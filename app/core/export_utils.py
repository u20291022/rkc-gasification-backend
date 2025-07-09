from tortoise.expressions import Q, Case, When, F
from tortoise.functions import Lower
from typing import Optional, List, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from fastapi import HTTPException
from app.models.models import AddressV2, TypeValue, FieldType, GazificationData, Municipality
from app.core.utils import log_db_operation


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
    from tortoise import Tortoise
    
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
        WHERE gd.id_type_address IN (3, 4, 6, 7, 8) 
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


async def get_optimized_gazification_data(
    mo_id: Optional[int] = None,
    district: Optional[str] = None,
    street: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    export_type: str = "excel",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[int, Dict[int, str]]]:
    """
    Оптимизированная функция получения данных о газификации
    """
    return await get_gazification_data(
        mo_id=mo_id,
        district=district,
        street=street,
        date_from=date_from,
        date_to=date_to,
    )
