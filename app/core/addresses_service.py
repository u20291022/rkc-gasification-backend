import asyncpg
from app.core.config import settings, addresses_connection_pool
from app.core.logging import get_logger, categorize_log, LogCategory
from contextlib import asynccontextmanager
from typing import Optional

logger = get_logger("addresses_service")

class AddressesService:
    """Сервис для работы с базой данных addresses через asyncpg"""
    
    @staticmethod
    async def initialize_pool():
        """Инициализация пула соединений с базой данных addresses"""
        global addresses_connection_pool
        try:
            addresses_connection_pool = await asyncpg.create_pool(
                settings.ADDRESSES_DATABASE_URL, 
                min_size=2, 
                max_size=10
            )
            logger.info(categorize_log("Пул соединений с базой addresses создан", LogCategory.INIT))
        except Exception as e:
            logger.error(categorize_log(f"Ошибка создания пула соединений addresses: {e}", LogCategory.ERROR))
            raise
    
    @staticmethod
    async def close_pool():
        """Закрытие пула соединений"""
        global addresses_connection_pool
        if addresses_connection_pool:
            await addresses_connection_pool.close()
            logger.info(categorize_log("Пул соединений с базой addresses закрыт", LogCategory.INIT))
    
    @staticmethod
    @asynccontextmanager
    async def get_connection():
        """Получение соединения с базой данных addresses"""
        if not addresses_connection_pool:
            raise Exception("Пул соединений addresses не инициализирован")
        
        async with addresses_connection_pool.acquire() as connection:
            yield connection

def build_full_house_number(house_num: str, add_num1: str, add_num2: str, 
                           house_type: str, add_type1: str, add_type2: str) -> str:
    """Построение полного номера дома"""
    parts = []
    
    if house_type and house_num:
        parts.append(f"{house_type} {house_num}")
    elif house_num:
        parts.append(house_num)
    
    if add_type1 and add_num1:
        parts.append(f"{add_type1} {add_num1}")
    elif add_num1:
        parts.append(add_num1)
    
    if add_type2 and add_num2:
        parts.append(f"{add_type2} {add_num2}")
    elif add_num2:
        parts.append(add_num2)
    
    return " ".join(parts) if parts else "Без номера"
