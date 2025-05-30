from fastapi import APIRouter, HTTPException
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.core.addresses_service import AddressesService
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger, categorize_log, LogCategory
from datetime import datetime
from typing import Dict, Any

router = APIRouter()
logger = get_logger("addresses_health")

@router.get("/health", response_model=BaseResponse[Dict[str, Any]], 
           summary="Проверка здоровья сервиса адресных подсказок")
async def health_check():
    """Проверка состояния сервиса адресных подсказок и базы данных addresses"""
    try:
        log_db_operation("health_check", "addresses_service", {})
        
        async with AddressesService.get_connection() as connection:
            # Проверяем подключение к базе данных
            result = await connection.fetchrow("SELECT 1 as test, NOW() as db_time")
            
            # Проверяем основные таблицы
            tables_check = {}
            
            # Проверка таблицы as_addr_obj
            addr_obj_count = await connection.fetchrow(
                "SELECT COUNT(*) as count FROM as_addr_obj WHERE isactual = 1 AND isactive = 1"
            )
            tables_check['as_addr_obj'] = {
                'status': 'ok',
                'active_records': addr_obj_count['count'] if addr_obj_count else 0
            }
            
            # Проверка таблицы as_houses
            houses_count = await connection.fetchrow(
                "SELECT COUNT(*) as count FROM as_houses WHERE isactual = 1 AND isactive = 1"
            )
            tables_check['as_houses'] = {
                'status': 'ok',
                'active_records': houses_count['count'] if houses_count else 0
            }
            
            # Проверка таблицы as_apartments
            apartments_count = await connection.fetchrow(
                "SELECT COUNT(*) as count FROM as_apartments WHERE isactual = 1 AND isactive = 1"
            )
            tables_check['as_apartments'] = {
                'status': 'ok',
                'active_records': apartments_count['count'] if apartments_count else 0
            }
            
            health_info = {
                "service": "addresses",
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "database": {
                    "status": "connected",
                    "db_time": result['db_time'].isoformat() if result and result['db_time'] else None
                },
                "tables": tables_check,
                "version": "1.0.0"
            }
            
            logger.info(categorize_log("Проверка здоровья сервиса адресов выполнена успешно", LogCategory.SUCCESS))
            
            return create_response(health_info, "Сервис адресных подсказок работает нормально")
    
    except Exception as e:
        logger.error(categorize_log(f"Ошибка проверки здоровья сервиса: {e}", LogCategory.ERROR))
        
        error_info = {
            "service": "addresses",
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "version": "1.0.0"
        }
        
        raise HTTPException(status_code=503, detail=error_info)
