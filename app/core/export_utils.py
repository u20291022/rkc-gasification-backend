from tortoise.expressions import Q, Case, When, F
from tortoise.functions import Lower, Trim
from typing import Optional, List, Dict, Any, Tuple
from app.models.models import AddressV2, TypeValue, FieldType, GazificationData, Municipality
from app.core.utils import log_db_operation

async def get_gazification_data(
    mo_id: Optional[int] = None, 
    district: Optional[str] = None, 
    street: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Получает данные о газификации на основе фильтров
    
    Args:
        mo_id: ID муниципалитета (опционально)
        district: Название района (опционально)
        street: Название улицы (опционально)
        
    Returns:
        Tuple[List[Dict], List[Dict]]: (addresses, questions)
            - addresses: список адресов, соответствующих фильтрам
            - questions: список вопросов (TypeValue) для отображения в отчете
    """
    # Находим адреса, которые уже газифицированы (id_type_address = 3)
    gazified_addresses = await GazificationData.filter(
        id_type_address=3
    ).values_list('id_address', flat=True)
    
    # Базовый фильтр для адресов
    base_filter = Q(house__isnull=False) & ~Q(id__in=gazified_addresses)
    
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
    
    return addresses, questions
