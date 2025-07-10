from tortoise.expressions import Q, Case, When, F
from tortoise.functions import Lower
from typing import Optional, List, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from fastapi import HTTPException
from app.models.models import AddressV2, TypeValue, FieldType, GazificationData, Municipality, TypeAddress
from app.core.utils import log_db_operation
from tortoise import Tortoise


def parse_date(date_str, is_start=True):
    """
    Парсит строку даты в различных форматах
    
    Args:
        date_str: Строка с датой
        is_start: Если True, то для даты без времени устанавливается начало дня,
                 если False - конец дня
    
    Returns:
        datetime объект или None
    """
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt if is_start else dt + timedelta(days=1) - timedelta(microseconds=1)
    except ValueError:
        pass
    try:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        pass
    try:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Неверный формат даты: {date_str}")


async def get_gazification_data(
    mo_id: Optional[int] = None, 
    district: Optional[str] = None, 
    street: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[int, Dict[int, str]]]:
    """
    Получает данные о газификации на основе фильтров
    
    Args:
        mo_id: ID муниципалитета (опционально)
        district: Название района (опционально)
        street: Название улицы (опционально)
        date_from: Начальная дата для фильтрации (опционально)
        date_to: Конечная дата для фильтрации (опционально)
    Returns:
        Tuple[List[Dict], List[Dict], Dict[int, Dict[int, str]]]: (addresses, questions, answers)
            - addresses: список адресов, соответствующих фильтрам
            - questions: список вопросов (TypeValue) для отображения в отчете
            - answers: словарь ответов на вопросы по адресам, где ключ внешний - id адреса,
              ключ внутренний - id вопроса, значение - ответ"""
    # Оптимизированный запрос для получения последних записей по каждому адресу
    # Используем единый SQL запрос для получения всех данных сразу
    
    # Строим базовый фильтр для дат
    date_filter_sql = ""
    params = []
    
    if date_from:
        date_filter_sql = "AND gd.date_create >= $1"
        params.append(date_from)
    
    if date_to:
        if date_filter_sql:
            date_filter_sql += f" AND gd.date_create <= ${len(params) + 1}"
        else:
            date_filter_sql = "AND gd.date_create <= $1"
        params.append(date_to)
    
    # Получаем последние записи газификации для каждого адреса с дополнительными фильтрами
    district_filter_sql = ""
    mo_filter_sql = ""
    
    # Добавляем параметры в правильном порядке
    if district:
        district_param_num = len(params) + 1
        district_filter_sql = f"AND (LOWER(a.district) = LOWER(${district_param_num}) OR LOWER(a.city) = LOWER(${district_param_num}))"
        params.append(district)
    
    if mo_id is not None:
        mo_param_num = len(params) + 1
        mo_filter_sql = f"AND a.id_mo = ${mo_param_num}"
        params.append(mo_id)
    
    latest_gas_records_query = f"""
        SELECT 
            gd.id_address, gd.id_type_address, gd.date_create, gd.from_login,
            a.id_mo, a.district, a.city, a.street, a.house, a.flat, a.from_login as address_from_login
        FROM s_gazifikacia.t_gazifikacia_data gd
        JOIN s_gazifikacia.t_address_v2 a ON gd.id_address = a.id
        WHERE gd.id_type_address IN (3, 4, 6, 7) 
            AND gd.is_mobile = true 
            AND gd.deleted = false
            AND a.deleted = false
            AND a.house IS NOT NULL
            {mo_filter_sql}
            {district_filter_sql}
            {date_filter_sql}
        ORDER BY gd.date_create DESC
    """
    
    # Выполняем оптимизированный запрос
    connection = Tortoise.get_connection("default")
    combined_data = await connection.execute_query_dict(latest_gas_records_query, params)
    # Обрабатываем результаты запроса
    address_gas_info = {}
    gazification_status = {}
    temp_addresses = []
    
    for item in combined_data:
        address_id = item["id_address"]
        
        # Пропускаем, если уже обработали этот адрес (берем только самую свежую запись)
        if address_id in address_gas_info:
            continue
            
        type_address = item["id_type_address"]
        date_create = item["date_create"]
        from_login = item["from_login"]
        
        # Сохраняем информацию о газификации
        address_gas_info[address_id] = {
            "gas_type": type_address,
            "date_create": date_create,
            "from_login": from_login,
        }
        gazification_status[address_id] = type_address
        
        # Формируем информацию об адресе
        address = {
            "id": address_id,
            "id_mo": item["id_mo"],
            "district": item["district"],
            "city": item["city"],
            "street": item["street"] if item["street"] != "Нет улиц" else "",
            "house": item["house"],
            "flat": item["flat"] or "",
            "from_login": item["address_from_login"],
            "gas_type": type_address,
            "date_create": date_create,
            "gas_from_login": from_login,
        }
        temp_addresses.append(address)
    
    # Удаляем дубликаты адресов, оставляя только с самыми свежими данными газификации
    # Группируем адреса по ключу (mo_id, street, house, flat)
    address_groups = {}
    for address in temp_addresses:
        key = (address["id_mo"], address["street"], address["house"], address["flat"])
        if key not in address_groups:
            address_groups[key] = []
        address_groups[key].append(address)
    
    # Для каждой группы оставляем только адрес с самыми свежими данными газификации
    addresses = []
    for group in address_groups.values():
        if len(group) == 1:
            addresses.append(group[0])
        else:
            # Сортируем по дате создания данных газификации (самые свежие первыми)
            group.sort(key=lambda x: x["date_create"], reverse=True)
            addresses.append(group[0])
    
    # Применяем фильтр по улице, если он задан (district уже обработан в SQL)
    if street:
        filtered_addresses = []
        for address in addresses:
            normalized_street = street.strip().lower()
            address_street = (address.get("street") or "").strip().lower()
            if address_street == normalized_street:
                filtered_addresses.append(address)
        addresses = filtered_addresses

    # Получаем информацию о муниципалитетах
    mo_ids = {address["id_mo"] for address in addresses if address["id_mo"] is not None}
    if mo_ids:
        municipalities = await Municipality.filter(id__in=mo_ids).values("id", "name")
        mo_names = {mo["id"]: mo["name"] for mo in municipalities}
        
        # Добавляем название муниципалитета к каждому адресу
        for address in addresses:
            mo_id = address.get("id_mo")
            if mo_id and mo_id in mo_names:
                address["mo_name"] = mo_names[mo_id]
            else:
                address["mo_name"] = "Неизвестный муниципалитет"
    else:
        for address in addresses:
            address["mo_name"] = "Неизвестный муниципалитет"
    
    # Получаем типы полей для фильтрации
    field_types = await FieldType.all()
    field_type_mapping = {ft.field_type_id: ft.field_type_name for ft in field_types}
    info_field_type_ids = [
        field_id for field_id, name in field_type_mapping.items() if name == "info"
    ]
    
    # Получаем вопросы для мобильного приложения
    questions = (
        await TypeValue.filter(for_mobile=True)
        .exclude(field_type_id__in=info_field_type_ids)
        .order_by("order")
        .values("id", "type_value", "description", "field_type_id")
    )
    for question in questions:
        field_type_id = question.get("field_type_id")
        if field_type_id:
            question["field_type"] = field_type_mapping.get(field_type_id)
    # Оптимизированное получение ответов - только последние ответы по каждому адресу и вопросу
    address_ids = [address["id"] for address in addresses]
    answers = {}
    
    if address_ids:
        # Используем SQL для получения последних ответов по каждому адресу и типу вопроса
        answers_params = []
        date_filter_answers = ""
        
        if date_from:
            date_filter_answers = "AND date_create >= $2"
            answers_params.append(date_from)
            
        if date_to:
            if date_filter_answers:
                date_filter_answers += f" AND date_create <= ${len(answers_params) + 2}"
            else:
                date_filter_answers = "AND date_create <= $2"
            answers_params.append(date_to)
        
        latest_answers_query = f"""
            SELECT DISTINCT ON (id_address, id_type_value) 
                id_address, id_type_value, value
            FROM s_gazifikacia.t_gazifikacia_data 
            WHERE id_address = ANY($1)
                AND id_type_value IS NOT NULL 
                AND is_mobile = true 
                AND deleted = false
                {date_filter_answers}
            ORDER BY id_address, id_type_value, date_create DESC
        """
        
        answers_data = await connection.execute_query_dict(
            latest_answers_query, 
            [address_ids] + answers_params
        )
        
        for answer in answers_data:
            address_id = answer["id_address"]
            type_value_id = answer["id_type_value"]
            value = answer["value"]
            if value and value.lower() == "true":
                value = "Да"
            elif value and value.lower() == "false":
                value = "Нет"
            if address_id not in answers:
                answers[address_id] = {}
            answers[address_id][type_value_id] = value
    log_db_operation(
        "read",
        "export_data",
        {
            "mo_id": mo_id,
            "district": district,
            "street": street,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "addresses_count": len(addresses),
            "questions_count": len(questions),
            "answers_count": len(answers),
        },
    )
    
    return addresses, questions, answers


async def get_activity_data(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Получает данные активности пользователей
    
    Args:
        date_from: Начальная дата для фильтрации (опционально)
        date_to: Конечная дата для фильтрации (опционально)
        
    Returns:
        List[Dict[str, Any]]: список записей активности
    """
    from app.models.models import Activity
    query = Activity.all()
    if date_from:
        query = query.filter(date_create__gte=date_from)
    if date_to:
        query = query.filter(date_create__lte=date_to)
    activities = await query.order_by('-date_create').values(
        'email', 'activity_count', 'date_create'
    )
    log_db_operation("read", "Activity", {"count": len(activities)})
    return activities


async def get_gazification_view_data(
    mo_id: Optional[int] = None,
    district: Optional[str] = None,
    street: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Получает данные для представления газификации на основе SQL view.
    
    Эта функция воспроизводит логику SQL представления v_gazifikacia_data_10_07_2025
    для получения структурированных данных о газификации с разворачиванием ответов
    на вопросы в отдельные колонки.
    
    Args:
        mo_id: ID муниципалитета (опционально)
        district: Название района (опционально) 
        street: Название улицы (опционально)
        date_from: Начальная дата для фильтрации (опционально)
        date_to: Конечная дата для фильтрации (опционально)
    
    Returns:
        List[Dict[str, Any]]: список записей с данными газификации и развернутыми ответами
    """
    # Строим SQL запрос, воспроизводящий логику представления
    connection = Tortoise.get_connection("default")
    
    # Собираем все параметры и условия в правильном порядке
    params = []
    where_conditions = []
    
    # Фильтры для дат газификации
    if date_from:
        params.append(date_from)
        where_conditions.append(f"gd.date_create >= ${len(params)}")
    
    if date_to:
        params.append(date_to)
        where_conditions.append(f"gd.date_create <= ${len(params)}")
    
    date_filter_sql = ""
    if where_conditions:
        date_filter_sql = "AND " + " AND ".join(where_conditions)
    
    # Фильтры для адресов
    address_where_conditions = []
    
    if mo_id is not None:
        params.append(mo_id)
        address_where_conditions.append(f"a.id_mo = ${len(params)}")
    
    if district:
        params.append(district)
        address_where_conditions.append(f"(LOWER(a.district) = LOWER(${len(params)}) OR LOWER(a.city) = LOWER(${len(params)}))")
    
    if street:
        params.append(street)
        address_where_conditions.append(f"LOWER(a.street) = LOWER(${len(params)})")
    
    address_filter_sql = ""
    if address_where_conditions:
        address_filter_sql = "AND " + " AND ".join(address_where_conditions)
    
    # Основной SQL запрос, основанный на представлении
    query = f"""
    WITH 
    gazifikaciaexport_0 as (
        SELECT *
        FROM s_gazifikacia.t_gazifikacia_data gd
        WHERE 
            gd.id_type_address IS NOT NULL
            AND gd.is_mobile = true 
            AND gd.deleted = false
            {date_filter_sql}
    ),
    addressexport_0 as (
        SELECT *
        FROM s_gazifikacia.t_address_v2 a
        WHERE 
            a.deleted = false
            AND a.house IS NOT NULL
            {address_filter_sql}
    ),
    addressexport_1 as (
        SELECT *
        FROM addressexport_0 a
        WHERE id in (   
            SELECT id
            FROM (
                SELECT id,
                    ROW_NUMBER() OVER (
                        PARTITION BY id_mo, street, house, flat
                        ORDER BY date_create DESC
                    ) AS rn
                FROM addressexport_0 a3
            ) a1
            WHERE a1.rn = 1
        )
    ),
    _gazifikacia AS (
        SELECT gd.id,
            gd.id_address,
            gd.id_type_address,
            gd.id_type_value,
            gd.value,
            gd.date_doc,
            gd.date_create,
            gd.date,
            gd.is_mobile,
            gd.from_login,
            gd.deleted
        FROM gazifikaciaexport_0 gd
    ), 
    _address AS (
        SELECT a.id,
            a.id_mo,
            a.city,
            a.street,
            a.house,
            a.flat,
            a.district,
            a.id_parent,
            a.mkd,
            a.is_mobile,
            a.date_create,
            a.from_login,
            a.deleted
        FROM addressexport_1 a
    ), 
    latest_gas_records AS (
        SELECT *
        FROM (
            SELECT gd.id_address,
                gd.id_type_address,
                gd.date_create,
                gd.from_login AS gas_from_login,
                gd.is_mobile,
                a.id_mo,
                a.district,
                a.city,
                CASE
                    WHEN a.street = 'Нет улиц' THEN ''
                    ELSE COALESCE(a.street, '')
                END AS street,
                a.house,
                COALESCE(a.flat, '') AS flat,
                a.from_login AS address_from_login,
                COALESCE(m.name, 'Неизвестный муниципалитет') AS mo_name,
                row_number() OVER (PARTITION BY gd.id_address ORDER BY gd.date_create DESC) AS rn
            FROM _gazifikacia gd
            JOIN _address a ON gd.id_address = a.id
            LEFT JOIN sp_s_subekty.v_all_name_mo m ON a.id_mo = m.id
            WHERE (gd.id_type_address = ANY (ARRAY[3, 4, 6, 7])) 
            AND a.house IS NOT null
        ) t
        WHERE t.rn = 1
    ), 
    latest_answers AS (
        SELECT DISTINCT ON (gd.id_address, gd.id_type_value) 
            gd.id_address,
            gd.id_type_value,
            gd.value
        FROM _gazifikacia gd
        WHERE gd.id_type_value IS NOT NULL
        ORDER BY gd.id_address, gd.id_type_value, gd.date_create DESC
    ), 
    pivot_answers AS (
        SELECT g.id_address,
            max(CASE WHEN g.id_type_value = 0 THEN g.value ELSE NULL END) AS date,
            max(CASE WHEN g.id_type_value = 1 THEN g.value ELSE NULL END) AS podal_zaivku,
            max(CASE WHEN g.id_type_value = 2 THEN g.value ELSE NULL END) AS doc_na_domovladenie,
            max(CASE WHEN g.id_type_value = 3 THEN g.value ELSE NULL END) AS doc_na_zem_ych,
            max(CASE WHEN g.id_type_value = 4 THEN g.value ELSE NULL END) AS est_otdeln_zjil_pomech,
            max(CASE WHEN g.id_type_value = 5 THEN g.value ELSE NULL END) AS soc_potderhka,
            max(CASE WHEN g.id_type_value = 6 THEN g.value ELSE NULL END) AS proinformirovan_new_ystr,
            max(CASE WHEN g.id_type_value = 7 THEN g.value ELSE NULL END) AS proinformirovan_new_org,
            max(CASE WHEN g.id_type_value = 8 THEN g.value ELSE NULL END) AS planiryet_podkluchits,
            max(CASE WHEN g.id_type_value = 9 THEN g.value ELSE NULL END) AS prichina,
            max(CASE WHEN g.id_type_value = 10 THEN g.value ELSE NULL END) AS buklet_s_kontaktami,
            max(CASE WHEN g.id_type_value = 11 THEN g.value ELSE NULL END) AS tekychi_sposob_otoplenia,
            max(CASE WHEN g.id_type_value = 12 THEN g.value ELSE NULL END) AS prichina_nehelania,
            max(CASE WHEN g.id_type_value = 13 THEN g.value ELSE NULL END) AS sposob_otoplenia
        FROM latest_answers g
        GROUP BY g.id_address
    )
    SELECT lgr.id_address,
        lgr.id_mo,
        lgr.mo_name AS name_mo,
        lgr.city,
        lgr.street,
        lgr.house,
        lgr.flat,
        lgr.district,
        to_char(lgr.date_create, 'DD.MM.YYYY HH24:MI') AS date_doc,
        lgr.id_type_address,
        tta.type_address,
        lgr.is_mobile,
        pa.date,
        pa.podal_zaivku,
        pa.doc_na_domovladenie,
        pa.doc_na_zem_ych,
        pa.est_otdeln_zjil_pomech,
        pa.soc_potderhka,
        pa.proinformirovan_new_ystr,
        pa.proinformirovan_new_org,
        pa.planiryet_podkluchits,
        pa.prichina,
        pa.buklet_s_kontaktami,
        pa.tekychi_sposob_otoplenia,
        pa.prichina_nehelania,
        pa.sposob_otoplenia
    FROM latest_gas_records lgr
    LEFT JOIN pivot_answers pa ON lgr.id_address = pa.id_address
    LEFT JOIN s_gazifikacia.t_type_address tta ON tta.id = lgr.id_type_address
    ORDER BY lgr.id_mo, lgr.district, lgr.street, lgr.house, lgr.flat
    """
    
    # Выполняем запрос
    result = await connection.execute_query_dict(query, params)
    
    # Нормализуем данные и преобразуем boolean значения
    for row in result:
        # Преобразуем boolean значения в читаемый формат
        for field in ["podal_zaivku", "doc_na_domovladenie", "doc_na_zem_ych", 
                     "est_otdeln_zjil_pomech", "soc_potderhka", "proinformirovan_new_ystr",
                     "proinformirovan_new_org", "planiryet_podkluchits", "buklet_s_kontaktami"]:
            value = row.get(field)
            if value and value.lower() == "true":
                row[field] = "Да"
            elif value and value.lower() == "false":
                row[field] = "Нет"
            elif not value:
                row[field] = ""
    
    log_db_operation(
        "read",
        "gazification_view_data",
        {
            "mo_id": mo_id,
            "district": district,
            "street": street,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "records_count": len(result),
        },
    )
    
    return result
