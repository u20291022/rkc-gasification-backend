"""
Модуль для оптимизации экспорта больших объемов данных
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import date
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import logging
from app.core.export_config import get_batch_size, get_optimization_config

logger = logging.getLogger(__name__)
config = get_optimization_config()

async def process_addresses_batch(
    addresses_batch: List[Dict[str, Any]], 
    address_gas_info: Dict[int, Dict[str, Any]], 
    mo_names: Dict[int, str]
) -> List[Dict[str, Any]]:
    """
    Обрабатывает пакет адресов в отдельном потоке
    """
    def process_batch():
        filtered_addresses = []
        
        for address in addresses_batch:
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
        
        return filtered_addresses
    
    # Выполняем обработку в отдельном потоке для CPU-intensive операций
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(executor, process_batch)
    
    return result

async def process_addresses_parallel(
    addresses: List[Dict[str, Any]], 
    address_gas_info: Dict[int, Dict[str, Any]], 
    mo_names: Dict[int, str],
    batch_size: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Обрабатывает большие списки адресов параллельно пакетами
    """
    if batch_size is None:
        batch_size = get_batch_size()
    
    if len(addresses) < batch_size:
        # Для маленьких списков используем простую обработку
        return await process_addresses_batch(addresses, address_gas_info, mo_names)
    
    # Разбиваем на пакеты
    batches = [addresses[i:i + batch_size] for i in range(0, len(addresses), batch_size)]
    
    # Ограничиваем количество параллельных задач
    max_workers = config.get("max_workers", 4)
    semaphore = asyncio.Semaphore(max_workers)
    
    async def process_batch_with_semaphore(batch):
        async with semaphore:
            return await process_addresses_batch(batch, address_gas_info, mo_names)
    
    # Обрабатываем пакеты параллельно
    tasks = [process_batch_with_semaphore(batch) for batch in batches]
    
    results = await asyncio.gather(*tasks)
    
    # Объединяем результаты
    filtered_addresses = []
    for result in results:
        filtered_addresses.extend(result)
    
    if config.get("performance_logging", {}).get("enabled", False):
        logger.info(f"Processed {len(addresses)} addresses in {len(batches)} batches, result: {len(filtered_addresses)} addresses")
    
    return filtered_addresses

def create_excel_data_vectorized(
    addresses: List[Dict[str, Any]], 
    questions: List[Dict[str, Any]], 
    answers: Dict[int, Dict[int, str]]
) -> List[Dict[str, Any]]:
    """
    Создает данные для Excel используя векторизованные операции
    """
    # Предварительно подготавливаем данные для быстрого доступа
    gas_status_map = {3: "Да", 6: "Адрес не существует", 4: "Нет", 7: "Нет"}
    question_columns = [(q['id'], q.get('type_value', f"Вопрос {q['id']}")) for q in questions]
    
    # Создаем базовые колонки для всех строк
    base_columns = [
        'Дата создания', 'Создатель адреса', 'Отправитель', 
        'Муниципалитет', 'Район', 'Улица', 'Дом', 'Квартира', 'Газифицирован?'
    ]
    
    # Создаем все колонки для вопросов
    all_columns = base_columns + [col_name for _, col_name in question_columns]
    
    # Предварительно создаем структуру данных
    data = []
    
    for address in addresses:
        # Быстрое определение статуса газификации
        gas_status = gas_status_map.get(address.get('gas_type'), "Нет")
        
        # Оптимизированное форматирование даты
        date_create_formatted = None
        date_create = address.get('date_create')
        if date_create:
            try:
                from datetime import timedelta
                date_with_offset = date_create + timedelta(hours=7)
                date_create_formatted = date_with_offset.strftime("%d.%m.%Y %H:%M")
            except:
                date_create_formatted = str(date_create)
        
        # Определяем район/город
        district_city = address.get('district') or address.get('city') or 'Не указан'
        
        # Создаем строку данных
        row = [
            date_create_formatted,
            address.get('from_login') or 'Отсутствует',
            address.get('gas_from_login') or 'Отсутствует',
            address.get('mo_name', 'Не указан'),
            district_city,
            address.get('street') or 'Не указана',
            address.get('house', 'Не указан'),
            address.get('flat', ''),
            gas_status,
        ]
        
        # Добавляем ответы на вопросы
        address_id = address['id']
        address_answers = answers.get(address_id, {})
        
        for question_id, _ in question_columns:
            row.append(address_answers.get(question_id, ''))
        
        # Создаем словарь из строки
        row_dict = dict(zip(all_columns, row))
        data.append(row_dict)
    
    return data

async def create_optimized_dataframe(data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Создает DataFrame с оптимизированными типами данных
    """
    def create_df():
        df = pd.DataFrame(data)
        
        # Оптимизируем типы данных для экономии памяти
        for col in df.columns:
            if df[col].dtype == 'object':
                # Проверяем, можно ли использовать category для экономии памяти
                unique_ratio = df[col].nunique() / len(df)
                if unique_ratio < 0.5:  # Если менее 50% уникальных значений
                    df[col] = df[col].astype('category')
        
        return df
    
    # Выполняем создание DataFrame в отдельном потоке
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        df = await loop.run_in_executor(executor, create_df)
    
    return df
