from tortoise.expressions import Q, Case, When, F
from tortoise.functions import Lower, Trim
from typing import Optional, List, Dict, Any, Tuple
from app.models.models import AddressV2, TypeValue, FieldType, GazificationData, Municipality
from app.core.utils import log_db_operation

async def get_gazification_data(
    mo_id: Optional[int] = None, 
    district: Optional[str] = None, 
    street: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[int, Dict[int, str]]]:
    """
    Получает данные о газификации на основе фильтров
    
    Args:
        mo_id: ID муниципалитета (опционально)
        district: Название района (опционально)
        street: Название улицы (опционально)
        
    Returns:
        Tuple[List[Dict], List[Dict], Dict[int, Dict[int, str]]]: (addresses, questions, answers)
            - addresses: список адресов, соответствующих фильтрам
            - questions: список вопросов (TypeValue) для отображения в отчете
            - answers: словарь ответов на вопросы по адресам, где ключ внешний - id адреса, 
              ключ внутренний - id вопроса, значение - ответ
    """    # Находим адреса, которые имеют статус газификации (id_type_address = 3 или 4)
    gazification_status = {}
    
    # Получаем данные о статусе газификации для адресов
    gas_status_data = await GazificationData.filter(
        id_type_address__in=[3, 4]
    ).values('id_address', 'id_type_address')
    
    # Создаем словарь {id_address: id_type_address}
    for item in gas_status_data:
        address_id = item['id_address']
        type_address = item['id_type_address']
        gazification_status[address_id] = type_address
    
    # Получаем список адресов с информацией о газификации
    addresses_with_gas_info = list(gazification_status.keys())
    
    # Базовый фильтр для адресов
    base_filter = Q(house__isnull=False) & Q(id__in=addresses_with_gas_info)
    
    # Добавляем фильтры на основе переданных параметров
    if mo_id is not None:
        base_filter = base_filter & Q(id_mo=mo_id)
    
    # Строим запрос для получения адресов
    query = AddressV2.filter(base_filter)
    
    # Если указан район, добавляем фильтр
    if district:
        normalized_district = district.strip().lower()
        query = query.annotate(
            district_lower=Lower(Trim("district")),
            city_lower=Lower(Trim("city"))
        ).filter(
            (Q(district_lower=normalized_district)) | 
            (Q(district__isnull=True) & Q(city_lower=normalized_district))
        )
    
    # Если указана улица, добавляем фильтр
    if street:
        normalized_street = street.strip().lower()
        query = query.annotate(
            street_lower=Lower(Trim("street"))
        ).filter(street_lower=normalized_street)
      # Получаем все подходящие адреса
    addresses = await query.values(
        'id', 'id_mo', 'district', 'city', 'street', 'house', 'flat'
    )
    
    log_db_operation("read", "AddressV2", {
        "mo_id": mo_id, 
        "district": district, 
        "street": street,
        "count": len(addresses)
    })
    
    # Добавляем информацию о статусе газификации к адресам
    for address in addresses:
        if address['street'] == 'Нет улиц':
            address['street'] = ''

        address_id = address['id']
        if address_id in gazification_status:
            address['gas_type'] = gazification_status[address_id]
    
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
    
    # Получаем ответы на вопросы для найденных адресов
    address_ids = [address['id'] for address in addresses]
    answers_data = await GazificationData.filter(
        id_address__in=address_ids,
        id_type_value__isnull=False
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
