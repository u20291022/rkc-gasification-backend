"""
Скрипт оптимизации базы данных для ускорения экспорта
"""
from tortoise import connections
import logging

logger = logging.getLogger(__name__)

async def create_export_indexes():
    """
    Создает индексы для ускорения запросов при экспорте
    """
    conn = connections.get("default")
    
    # Индексы для таблицы адресов
    address_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_address_v2_mo_mobile ON s_gazifikacia.t_address_v2(id_mo) WHERE is_mobile = true;",
        "CREATE INDEX IF NOT EXISTS idx_address_v2_house_not_null ON s_gazifikacia.t_address_v2(house) WHERE house IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_address_v2_district_city ON s_gazifikacia.t_address_v2(district, city);",
        "CREATE INDEX IF NOT EXISTS idx_address_v2_street ON s_gazifikacia.t_address_v2(street);",
        "CREATE INDEX IF NOT EXISTS idx_address_v2_from_login ON s_gazifikacia.t_address_v2(from_login);",
    ]
    
    # Индексы для таблицы данных газификации
    gazification_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_gazification_data_address_type ON s_gazifikacia.t_gazifikacia_data(id_address, id_type_address);",
        "CREATE INDEX IF NOT EXISTS idx_gazification_data_mobile_date ON s_gazifikacia.t_gazifikacia_data(is_mobile, date_create) WHERE is_mobile = true;",
        "CREATE INDEX IF NOT EXISTS idx_gazification_data_type_value ON s_gazifikacia.t_gazifikacia_data(id_type_value) WHERE id_type_value IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_gazification_data_type_address_mobile ON s_gazifikacia.t_gazifikacia_data(id_type_address, is_mobile);",
        "CREATE INDEX IF NOT EXISTS idx_gazification_data_date_create ON s_gazifikacia.t_gazifikacia_data(date_create);",
    ]
    
    # Составной индекс для оптимизации основного запроса экспорта
    composite_indexes = [
        """CREATE INDEX IF NOT EXISTS idx_gazification_export_composite 
           ON s_gazifikacia.t_gazifikacia_data(id_type_address, is_mobile, date_create) 
           WHERE id_type_address IN (3, 4, 6, 7) AND is_mobile = true;""",
        
        """CREATE INDEX IF NOT EXISTS idx_address_export_composite 
           ON s_gazifikacia.t_address_v2(id_mo, district, city, street, house) 
           WHERE house IS NOT NULL;""",
    ]
    
    all_indexes = address_indexes + gazification_indexes + composite_indexes
    
    for index_sql in all_indexes:
        try:
            await conn.execute_query(index_sql)
            logger.info(f"Создан индекс: {index_sql[:50]}...")
        except Exception as e:
            logger.warning(f"Не удалось создать индекс: {str(e)}")

async def optimize_database_settings():
    """
    Оптимизирует настройки базы данных для экспорта
    """
    conn = connections.get("default")
    
    optimization_queries = [
        # Увеличиваем work_mem для сложных запросов
        "SET work_mem = '256MB';",
        
        # Оптимизируем настройки для сортировки
        "SET maintenance_work_mem = '512MB';",
        
        # Включаем параллельные запросы если доступно
        "SET max_parallel_workers_per_gather = 2;",
        
        # Оптимизируем random_page_cost для SSD
        "SET random_page_cost = 1.1;",
    ]
    
    for query in optimization_queries:
        try:
            await conn.execute_query(query)
            logger.info(f"Применена оптимизация: {query}")
        except Exception as e:
            logger.warning(f"Не удалось применить оптимизацию: {str(e)}")

async def analyze_tables():
    """
    Обновляет статистику таблиц для оптимизатора запросов
    """
    conn = connections.get("default")
    
    tables_to_analyze = [
        "s_gazifikacia.t_address_v2",
        "s_gazifikacia.t_gazifikacia_data",
        "s_gazifikacia.t_type_value",
        "s_gazifikacia.field_type",
    ]
    
    for table in tables_to_analyze:
        try:
            await conn.execute_query(f"ANALYZE {table};")
            logger.info(f"Обновлена статистика для таблицы: {table}")
        except Exception as e:
            logger.warning(f"Не удалось обновить статистику для {table}: {str(e)}")

async def run_database_optimization():
    """
    Запускает полную оптимизацию базы данных
    """
    logger.info("Начинаем оптимизацию базы данных для экспорта...")
    
    try:
        await create_export_indexes()
        await optimize_database_settings()
        await analyze_tables()
        logger.info("Оптимизация базы данных завершена успешно")
    except Exception as e:
        logger.error(f"Ошибка при оптимизации базы данных: {str(e)}")
        raise

# Функция для проверки эффективности индексов
async def check_index_usage():
    """
    Проверяет использование созданных индексов
    """
    conn = connections.get("default")
    
    check_query = """
    SELECT 
        schemaname,
        tablename,
        indexname,
        idx_tup_read,
        idx_tup_fetch
    FROM pg_stat_user_indexes 
    WHERE schemaname = 's_gazifikacia'
    AND indexname LIKE 'idx_%'
    ORDER BY idx_tup_read DESC;
    """
    
    try:
        result = await conn.execute_query(check_query)
        logger.info("Статистика использования индексов:")
        for row in result:
            logger.info(f"Индекс {row[2]}: читано {row[3]}, извлечено {row[4]}")
        return result
    except Exception as e:
        logger.error(f"Ошибка при проверке индексов: {str(e)}")
        return []
