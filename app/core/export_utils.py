from tortoise.expressions import Q, Case, When, F
from tortoise.functions import Lower
from typing import Optional, List, Dict, Any, Tuple
from datetime import date, datetime
from app.models.models import AddressV2, TypeValue, FieldType, GazificationData, Municipality
from app.core.utils import log_db_operation

async def get_gazification_data(
    mo_id: Optional[int] = None, 
    district: Optional[str] = None, 
    street: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    only_new_records: bool = False,
    last_export_date: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[int, Dict[int, str]]]:
    """
    Получает данные о газификации на основе фильтров
    
    Args:
        mo_id: ID муниципалитета (опционально)
        district: Название района (опционально)
        street: Название улицы (опционально)
        date_from: Начальная дата для фильтрации (опционально)
        date_to: Конечная дата для фильтрации (опционально)
        only_new_records: Флаг для получения только новых записей (опционально)
        last_export_date: Дата последней выгрузки для фильтрации новых записей (опционально)
    Returns:
        Tuple[List[Dict], List[Dict], Dict[int, Dict[int, str]]]: (addresses, questions, answers)
            - addresses: список адресов, соответствующих фильтрам
            - questions: список вопросов (TypeValue) для отображения в отчете
            - answers: словарь ответов на вопросы по адресам, где ключ внешний - id адреса,
              ключ внутренний - id вопроса, значение - ответ"""
    # Построение базового фильтра для данных газификации
    gas_data_filter = Q(id_type_address__in=[3, 4, 6, 7, 8]) & Q(is_mobile=True) & Q(deleted=False)
    
    # Применение фильтров по датам
    if only_new_records and last_export_date:
        gas_data_filter = gas_data_filter & Q(date_create__gt=last_export_date)
    elif date_from:
        gas_data_filter = gas_data_filter & Q(date_create__gte=date_from)
    if date_to:
        gas_data_filter = gas_data_filter & Q(date_create__lte=date_to)
    
    # Оптимизированный запрос для получения последних записей по каждому адресу
    # Используем единый SQL запрос для получения всех данных сразу
    from tortoise import Tortoise
    
    # Строим базовый фильтр для дат
    date_filter_sql = ""
    params = []
    
    if only_new_records and last_export_date:
        date_filter_sql = "AND date_create > %s"
        params.append(last_export_date)
    elif date_from:
        date_filter_sql = "AND date_create >= %s"
        params.append(date_from)
    
    if date_to:
        if date_filter_sql:
            date_filter_sql += " AND date_create <= %s"
        else:
            date_filter_sql = "AND date_create <= %s"
        params.append(date_to)
    
    # Получаем последние записи газификации для каждого адреса с дополнительными фильтрами
    latest_gas_records_query = f"""
        SELECT DISTINCT ON (gd.id_address) 
            gd.id_address, gd.id_type_address, gd.date_create, gd.from_login,
            a.id_mo, a.district, a.city, a.street, a.house, a.flat, a.from_login as address_from_login
        FROM s_gazifikacia.t_gazifikacia_data gd
        JOIN s_gazifikacia.t_address_v2 a ON gd.id_address = a.id
        WHERE gd.id_type_address IN (3, 4, 6, 7, 8) 
            AND gd.is_mobile = true 
            AND gd.deleted = false
            AND a.deleted = false
            AND a.house IS NOT NULL
            {("AND a.id_mo = %s" if mo_id is not None else "")}
            {date_filter_sql}
        ORDER BY gd.id_address, gd.date_create DESC
    """
    
    # Добавляем параметр mo_id если нужно
    if mo_id is not None:
        params.insert(-len([p for p in [date_from, date_to] if p is not None]) if date_filter_sql else 0, mo_id)
    
    # Выполняем оптимизированный запрос
    connection = Tortoise.get_connection("default")
    combined_data = await connection.execute_query_dict(latest_gas_records_query, params)
    # Обрабатываем результаты запроса
    address_gas_info = {}
    gazification_status = {}
    addresses = []
    
    for item in combined_data:
        address_id = item["id_address"]
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
        addresses.append(address)
    
    # Применяем фильтры по району и улице, если они заданы
    if district or street:
        filtered_addresses = []
        for address in addresses:
            if district:
                normalized_district = district.strip().lower()
                address_district = (address.get("district") or "").strip().lower()
                address_city = (address.get("city") or "").strip().lower()
                if not (address_district == normalized_district or address_city == normalized_district):
                    continue
            
            if street:
                normalized_street = street.strip().lower()
                address_street = (address.get("street") or "").strip().lower()
                if address_street != normalized_street:
                    continue
                    
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
        
        if only_new_records and last_export_date:
            date_filter_answers = "AND date_create > %s"
            answers_params.append(last_export_date)
        elif date_from:
            date_filter_answers = "AND date_create >= %s"
            answers_params.append(date_from)
            
        if date_to:
            if date_filter_answers:
                date_filter_answers += " AND date_create <= %s"
            else:
                date_filter_answers = "AND date_create <= %s"
            answers_params.append(date_to)
        
        latest_answers_query = f"""
            SELECT DISTINCT ON (id_address, id_type_value) 
                id_address, id_type_value, value
            FROM s_gazifikacia.t_gazifikacia_data 
            WHERE id_address = ANY(%s)
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
    only_new_since_last_export: bool = False,
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
        only_new_records=only_new_since_last_export,
        last_export_date=None  # Логика для получения последней даты экспорта убрана
    )
