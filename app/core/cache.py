"""
Модуль для кеширования часто используемых данных
"""
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import asyncio
from app.models.models import Municipality, FieldType, TypeValue
from app.core.export_config import get_cache_ttl

class DataCache:
    """Простой кеш для часто используемых данных"""
    
    def __init__(self, ttl_minutes: Optional[int] = None):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = timedelta(minutes=ttl_minutes or get_cache_ttl())
    
    def _is_expired(self, key: str) -> bool:
        """Проверяет, истек ли срок действия кеша"""
        if key not in self._cache:
            return True
        return datetime.now() - self._cache[key]['timestamp'] > self._ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Получает данные из кеша"""
        if self._is_expired(key):
            return None
        return self._cache[key]['data']
    
    def set(self, key: str, data: Any) -> None:
        """Сохраняет данные в кеш"""
        self._cache[key] = {
            'data': data,
            'timestamp': datetime.now()
        }
    
    def invalidate(self, key: str) -> None:
        """Удаляет данные из кеша"""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Очищает весь кеш"""
        self._cache.clear()

# Глобальный экземпляр кеша
_cache = DataCache()

async def get_municipalities_cached() -> Dict[int, str]:
    """Получает словарь муниципалитетов с кешированием"""
    cache_key = "municipalities"
    cached_data = _cache.get(cache_key)
    
    if cached_data is not None:
        return cached_data
    
    # Загружаем данные из БД
    municipalities = await Municipality.all().values('id', 'name')
    mo_dict = {mo['id']: mo['name'] for mo in municipalities}
    
    _cache.set(cache_key, mo_dict)
    return mo_dict

async def get_field_types_cached() -> Dict[int, str]:
    """Получает словарь типов полей с кешированием"""
    cache_key = "field_types"
    cached_data = _cache.get(cache_key)
    
    if cached_data is not None:
        return cached_data
    
    # Загружаем данные из БД
    field_types = await FieldType.all().values('field_type_id', 'field_type_name')
    field_type_dict = {ft['field_type_id']: ft['field_type_name'] for ft in field_types}
    
    _cache.set(cache_key, field_type_dict)
    return field_type_dict

async def get_questions_cached() -> tuple:
    """Получает вопросы с кешированием"""
    cache_key = "questions"
    cached_data = _cache.get(cache_key)
    
    if cached_data is not None:
        return cached_data
    
    # Загружаем типы полей
    field_type_mapping = await get_field_types_cached()
    
    info_field_type_ids = [field_id for field_id, name in field_type_mapping.items() 
                           if name == "info"]
    
    # Загружаем вопросы
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
        question['field_type'] = field_type_mapping.get(field_type_id) if field_type_id else None
    
    _cache.set(cache_key, questions)
    return questions

def invalidate_cache():
    """Очищает кеш (используется при изменении справочных данных)"""
    _cache.clear()

def invalidate_municipalities_cache():
    """Очищает кеш муниципалитетов"""
    _cache.invalidate("municipalities")

def invalidate_field_types_cache():
    """Очищает кеш типов полей"""
    _cache.invalidate("field_types")

def invalidate_questions_cache():
    """Очищает кеш вопросов"""
    _cache.invalidate("questions")
