from tortoise.expressions import Q, Case, When, F
from tortoise.functions import Lower
from typing import Optional, List, Dict, Any, Tuple
from datetime import date
from app.models.models import AddressV2, TypeValue, FieldType, GazificationData, Municipality
from app.core.utils import log_db_operation
from app.core.cache import get_municipalities_cached, get_field_types_cached, get_questions_cached
from app.core.export_optimization import process_addresses_parallel
from app.core.export_config import get_parallel_threshold

async def get_gazification_data(
    mo_id: Optional[int] = None, 
    district: Optional[str] = None, 
    street: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[int, Dict[int, str]]]:
    """
    Получает данные о газификации на основе фильтров (оптимизированная версия)
    
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
              ключ внутренний - id вопроса, значение - ответ
    """
    # ОПТИМИЗАЦИЯ 1: Используем SQL подзапрос для получения самой свежей записи по каждому адресу
    from tortoise.queryset import QuerySet
    from tortoise import connections
    
    # Создаем базовый фильтр для данных газификации (только мобильные)
    gas_data_filter = Q(id_type_address__in=[3, 4, 6, 7]) & Q(is_mobile=True)
    
    # Добавляем фильтрацию по датам, если указаны
    if date_from:
        gas_data_filter = gas_data_filter & Q(date_create__gte=date_from)
    if date_to:
        gas_data_filter = gas_data_filter & Q(date_create__lte=date_to)
    
    # ОПТИМИЗАЦИЯ 2: Получаем только самые свежие записи газификации через SQL
    # Используем window function для получения последней записи по каждому адресу
    gas_status_query = GazificationData.filter(gas_data_filter).annotate(
        row_number=F("row_number() OVER (PARTITION BY id_address ORDER BY date_create DESC)")
    ).filter(row_number=1).values(
        'id_address', 'id_type_address', 'date_create', 'from_login'
    )
    
    # Fallback на Python если window functions не поддерживаются
    try:
        gas_status_data = await gas_status_query
    except:
        # Используем старый метод с сортировкой в Python
        gas_status_data_all = await GazificationData.filter(gas_data_filter).order_by(
            'id_address', '-date_create'
        ).values('id_address', 'id_type_address', 'date_create', 'from_login')
        
        # Берем только первую (самую свежую) запись для каждого адреса
        seen_addresses = set()
        gas_status_data = []
        for item in gas_status_data_all:
            if item['id_address'] not in seen_addresses:
                gas_status_data.append(item)
                seen_addresses.add(item['id_address'])
    
    # ОПТИМИЗАЦИЯ 3: Создаем словари одним проходом
    address_gas_info = {
        item['id_address']: {
            'gas_type': item['id_type_address'],
            'date_create': item['date_create'],
            'from_login': item['from_login']
        }
        for item in gas_status_data
    }
    
    gazification_status = {addr_id: info['gas_type'] for addr_id, info in address_gas_info.items()}
    addresses_with_gas_info = list(address_gas_info.keys())    # ОПТИМИЗАЦИЯ 4: Объединяем фильтры и используем один запрос для получения адресов
    # Базовый фильтр для адресов (только мобильные)
    if addresses_with_gas_info:
        base_filter = Q(house__isnull=False) & Q(id__in=addresses_with_gas_info)
    else:
        base_filter = Q(house__isnull=False)
    
    # Добавляем фильтры на основе переданных параметров
    if mo_id is not None:
        base_filter = base_filter & Q(id_mo=mo_id)
    
    # Если указан район, добавляем фильтр
    if district:
        normalized_district = district.strip().lower()
        base_filter = base_filter & (
            (Q(district__icontains=normalized_district)) | 
            (Q(district__isnull=True) & Q(city__icontains=normalized_district))
        )
    
    # Если указана улица, добавляем фильтр
    if street:
        normalized_street = street.strip().lower()
        base_filter = base_filter & Q(street__icontains=normalized_street)
      # ОПТИМИЗАЦИЯ 5: Получаем адреса и кешированные названия муниципалитетов
    addresses = await AddressV2.filter(base_filter).values(
        'id', 'id_mo', 'district', 'city', 'street', 'house', 'flat', 'from_login'
    )
    
    # Получаем кешированные названия муниципалитетов
    mo_names = await get_municipalities_cached()
    
    log_db_operation("read", "AddressV2", {
        "mo_id": mo_id, 
        "district": district, 
        "street": street,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "count": len(addresses)
    })    # ОПТИМИЗАЦИЯ 6: Фильтруем и обогащаем адреса параллельно для больших объемов
    parallel_threshold = get_parallel_threshold()
    if len(addresses) > parallel_threshold:
        # Для больших объемов используем параллельную обработку
        addresses = await process_addresses_parallel(addresses, address_gas_info, mo_names)
    else:
        # Для маленьких объемов используем обычную обработку
        filtered_addresses = []
        for address in addresses:
            # Быстрая проверка и очистка данных
            district = (address.get('district') or '').strip() or None
            city = (address.get('city') or '').strip() or None
            street_val = (address.get('street') or '').strip() or None
            house = (address.get('house') or '').strip()
            flat = (address.get('flat') or '').strip() or None
            
            # Пропускаем записи где нет ни района, ни города, или нет дома
            if (not district and not city) or not house:
                continue
            
            # Специальная обработка для "Нет улиц"
            if street_val == 'Нет улиц':
                street_val = None
            
            # Создаем обогащенный адрес
            address_id = address['id']
            mo_id_val = address['id_mo']
            enriched_address = {
                'id': address_id,
                'id_mo': mo_id_val,
                'district': district,
                'city': city,
                'street': street_val,
                'house': house,
                'flat': flat,
                'from_login': address['from_login'],
                'mo_name': mo_names.get(mo_id_val, 'Неизвестный муниципалитет') if mo_id_val else 'Неизвестный муниципалитет'
            }
            
            # Добавляем информацию о газификации
            if address_id in address_gas_info:
                gas_info = address_gas_info[address_id]
                enriched_address.update({
                    'gas_type': gas_info['gas_type'],
                    'date_create': gas_info['date_create'],
                    'gas_from_login': gas_info['from_login']
                })
            
            filtered_addresses.append(enriched_address)
        
        addresses = filtered_addresses
    
    # ОПТИМИЗАЦИЯ 7: Получаем вопросы из кеша
    questions = await get_questions_cached()
    
    log_db_operation("read", "TypeValue", {"count": len(questions)})
    
    # ОПТИМИЗАЦИЯ 8: Получаем ответы оптимизированно
    if addresses:
        address_ids = [address['id'] for address in addresses]
        answers_data = await GazificationData.filter(
            id_address__in=address_ids,
            id_type_value__isnull=False,
            is_mobile=True
        ).values('id_address', 'id_type_value', 'value')
        
        # ОПТИМИЗАЦИЯ 9: Создаем словарь ответов оптимизированно
        answers = {}
        for answer in answers_data:
            address_id = answer['id_address']
            type_value_id = answer['id_type_value']
            value = answer['value']
            
            # Быстрая обработка булевых значений
            if value:
                if value.lower() == 'true':
                    value = 'Да'
                elif value.lower() == 'false':
                    value = 'Нет'
            
            if address_id not in answers:
                answers[address_id] = {}
                
            answers[address_id][type_value_id] = value
        
        log_db_operation("read", "GazificationData", {"count": len(answers_data)})
    else:
        answers = {}
    
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
        query = query.filter(date_create__lte=date_to)    # Получаем данные и сортируем по дате создания (по убыванию)
    activities = await query.order_by('-date_create').values(
        'email', 'activity_count', 'date_create'
    )
    
    log_db_operation("read", "Activity", {"count": len(activities)})
    
    return activities
