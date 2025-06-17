from tortoise.expressions import Q, Case, When, F
from tortoise.functions import Lower
from typing import Optional, List, Dict, Any, Tuple
from datetime import date
from app.models.models import AddressV2, TypeValue, FieldType, GazificationData, Municipality
from app.core.utils import log_db_operation

async def get_gazification_data(
    mo_id: Optional[int] = None, 
    district: Optional[str] = None, 
    street: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
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
              ключ внутренний - id вопроса, значение - ответ    """# Находим адреса, которые имеют статус газификации (id_type_address = 3 или 4)
    gazification_status = {}
      # Создаем базовый фильтр для данных газификации (только мобильные)
    gas_data_filter = Q(id_type_address__in=[3, 4]) & Q(is_mobile=True)
    
    # Добавляем фильтрацию по датам, если указаны
    if date_from:
        gas_data_filter = gas_data_filter & Q(date_create__gte=date_from)
    if date_to:
        gas_data_filter = gas_data_filter & Q(date_create__lte=date_to)
      # Получаем данные о статусе газификации для адресов
    gas_status_data = await GazificationData.filter(gas_data_filter).values(
        'id_address', 'id_type_address', 'date_create', 'from_login'
    )
      # Создаем словарь {id_address: {'gas_type': id_type_address, 'date_create': date, 'from_login': from_login}}
    address_gas_info = {}
    for item in gas_status_data:
        address_id = item['id_address']
        type_address = item['id_type_address']
        date_create = item['date_create']
        from_login = item['from_login']
        
        # Если для адреса уже есть запись, берем самую новую
        if address_id not in address_gas_info or date_create > address_gas_info[address_id]['date_create']:
            address_gas_info[address_id] = {
                'gas_type': type_address,
                'date_create': date_create,
                'from_login': from_login
            }
    gazification_status = {addr_id: info['gas_type'] for addr_id, info in address_gas_info.items()}
    
    # Получаем список адресов с информацией о газификации
    addresses_with_gas_info = list(gazification_status.keys())
      # Базовый фильтр для адресов (только мобильные)
    # Если есть адреса с газификацией, используем их, иначе берем все мобильные адреса с домами
    if addresses_with_gas_info:
        base_filter = Q(house__isnull=False) & Q(id__in=addresses_with_gas_info)
    else:
        base_filter = Q(house__isnull=False)
    
    # Добавляем фильтры на основе переданных параметров
    if mo_id is not None:
        base_filter = base_filter & Q(id_mo=mo_id)
    
    # Строим запрос для получения адресов
    query = AddressV2.filter(base_filter)
      # Если указан район, добавляем фильтр
    if district:
        normalized_district = district.strip().lower()
        query = query.annotate(
            district_lower=Lower("district"),
            city_lower=Lower("city")
        ).filter(
            (Q(district_lower=normalized_district)) | 
            (Q(district__isnull=True) & Q(city_lower=normalized_district))
        )
    
    # Если указана улица, добавляем фильтр
    if street:
        normalized_street = street.strip().lower()
        query = query.annotate(
            street_lower=Lower("street")
        ).filter(street_lower=normalized_street)    # Получаем все подходящие адреса
    addresses = await query.values(
        'id', 'id_mo', 'district', 'city', 'street', 'house', 'flat', 'from_login'
    )
    
    log_db_operation("read", "AddressV2", {
        "mo_id": mo_id, 
        "district": district, 
        "street": street,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "count": len(addresses)
    })    # Добавляем информацию о статусе газификации к адресам и фильтруем на Python
    filtered_addresses = []
    for address in addresses:
        # Фильтруем пустые строки и строки с пробелами на Python
        district = address.get('district', '').strip() if address.get('district') else ''
        city = address.get('city', '').strip() if address.get('city') else ''
        street = address.get('street', '').strip() if address.get('street') else ''
        house = address.get('house', '').strip() if address.get('house') else ''
        flat = address.get('flat', '').strip() if address.get('flat') else ''
        
        # Пропускаем записи где нет ни района, ни города, или нет дома
        if (not district and not city) or not house:
            continue
        
        # Обновляем данные в адресе
        address['district'] = district if district else None
        address['city'] = city if city else None
        address['street'] = street if street else None
        address['house'] = house if house else None
        address['flat'] = flat if flat else None
        if address['street'] == 'Нет улиц':
            address['street'] = ''

        address_id = address['id']
        if address_id in gazification_status:
            address['gas_type'] = gazification_status[address_id]
        if address_id in address_gas_info:
            address['date_create'] = address_gas_info[address_id]['date_create']
            address['gas_from_login'] = address_gas_info[address_id]['from_login']
        
        filtered_addresses.append(address)
    
    addresses = filtered_addresses
    
    # Получаем названия муниципалитетов для всех адресов
    mo_ids = {address['id_mo'] for address in addresses if address['id_mo'] is not None}
    municipalities = await Municipality.filter(id__in=mo_ids).values('id', 'name')
    mo_names = {mo['id']: mo['name'] for mo in municipalities}
      # Получаем вопросы для мобильного приложения и не типа "info"
    field_types = await FieldType.all()
    field_type_mapping = {ft.field_type_id: ft.field_type_name for ft in field_types}
    
    info_field_type_ids = [field_id for field_id, name in field_type_mapping.items() 
                           if name == "info"]
    
    questions = await TypeValue.filter(
        for_mobile=True
    ).exclude(
        field_type_id__in=info_field_type_ids
    ).order_by('order').values(
        'id', 'type_value', 'description', 'field_type_id'
    )
    
    # Добавляем названия типов полей
    for question in questions:
        field_type_id = question.get('field_type_id')
        if field_type_id:
            question['field_type'] = field_type_mapping.get(field_type_id)
    
    log_db_operation("read", "TypeValue", {"count": len(questions)})
      # Обогащаем адреса названиями муниципалитетов
    for address in addresses:
        mo_id = address.get('id_mo')
        if mo_id and mo_id in mo_names:
            address['mo_name'] = mo_names[mo_id]
        else:
            address['mo_name'] = "Неизвестный муниципалитет"
      # Получаем ответы на вопросы для найденных адресов (только мобильные)
    address_ids = [address['id'] for address in addresses]
    answers_data = await GazificationData.filter(
        id_address__in=address_ids,
        id_type_value__isnull=False,
        is_mobile=True
    ).values('id_address', 'id_type_value', 'value')
    
    # Форматируем ответы в виде словаря {id_address: {id_type_value: value}}
    answers = {}
    for answer in answers_data:
        address_id = answer['id_address']
        type_value_id = answer['id_type_value']
        value = answer['value']
        
        # Преобразуем true/false в Да/Нет
        if value and value.lower() == 'true':
            value = 'Да'
        elif value and value.lower() == 'false':
            value = 'Нет'
        
        if address_id not in answers:
            answers[address_id] = {}
            
        answers[address_id][type_value_id] = value
    
    log_db_operation("read", "GazificationData", {"count": len(answers_data)})
    
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
    
    # Создаем базовый запрос
    query = Activity.all()
    
    # Добавляем фильтрацию по датам, если указаны
    if date_from:
        query = query.filter(date_create__gte=date_from)
    if date_to:
        query = query.filter(date_create__lte=date_to)
    
    # Получаем данные и сортируем по дате создания (по убыванию)
    activities = await query.order_by('-date_create').values(
        'email', 'activity_count', 'date_create'
    )
    
    log_db_operation("read", "Activity", {"count": len(activities)})
    
    return activities
