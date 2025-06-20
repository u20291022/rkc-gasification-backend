"""
Настройки оптимизации экспорта данных
"""
from typing import Dict, Any

# Настройки для оптимизации экспорта
EXPORT_OPTIMIZATION_CONFIG: Dict[str, Any] = {
    # Размер пакета для параллельной обработки адресов
    "address_batch_size": 1000,
    
    # Порог для включения параллельной обработки
    "parallel_processing_threshold": 2000,
    
    # Порог для включения векторизованного создания данных Excel
    "vectorized_data_threshold": 1000,
    
    # Время жизни кеша в минутах
    "cache_ttl_minutes": 60,
    
    # Максимальное количество потоков для ThreadPoolExecutor
    "max_workers": 4,
    
    # Настройки для pandas и Excel
    "pandas_options": {
        "chunksize": 10000,
        "low_memory": True,
    },
    
    "excel_options": {
        "engine": "xlsxwriter",
        "options": {
            "strings_to_numbers": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        }
    },
    
    # Настройки форматирования Excel
    "excel_formatting": {
        "header_format": {
            "bold": True,
            "text_wrap": True,
            "valign": "top",
            "align": "center",
            "border": 1,
            "bg_color": "#D7E4BC"
        },
        "cell_format": {
            "border": 1,
            "text_wrap": True,
            "valign": "top"
        },
        "date_format": {
            "border": 1,
            "num_format": "dd.mm.yyyy hh:mm",
            "valign": "top"
        }
    },
    
    # Настройки колонок Excel
    "excel_columns": {
        "Дата создания": 18,
        "Муниципалитет": 25,
        "Район": 25,
        "Улица": 25,
        "Создатель адреса": 20,
        "Отправитель": 20,
        "default_width": 15,
        "max_width": 40
    },
    
    # Настройки логирования для отладки производительности
    "performance_logging": {
        "enabled": True,
        "log_slow_queries": True,
        "slow_query_threshold_seconds": 5,
        "log_memory_usage": False
    }
}

def get_optimization_config() -> Dict[str, Any]:
    """Возвращает конфигурацию оптимизации"""
    return EXPORT_OPTIMIZATION_CONFIG

def get_batch_size() -> int:
    """Возвращает размер пакета для обработки"""
    return EXPORT_OPTIMIZATION_CONFIG["address_batch_size"]

def get_parallel_threshold() -> int:
    """Возвращает порог для включения параллельной обработки"""
    return EXPORT_OPTIMIZATION_CONFIG["parallel_processing_threshold"]

def get_vectorized_threshold() -> int:
    """Возвращает порог для включения векторизованного создания данных"""
    return EXPORT_OPTIMIZATION_CONFIG["vectorized_data_threshold"]

def get_cache_ttl() -> int:
    """Возвращает время жизни кеша в минутах"""
    return EXPORT_OPTIMIZATION_CONFIG["cache_ttl_minutes"]
