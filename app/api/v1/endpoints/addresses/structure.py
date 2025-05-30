from fastapi import APIRouter, HTTPException, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.addresses import AddressStructure
from app.core.addresses_service import AddressesService
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger, categorize_log, LogCategory

router = APIRouter()
logger = get_logger("addresses_structure")

@router.get("/address-structure/{municipality_id}", response_model=BaseResponse[AddressStructure], 
           summary="Получить структуру адресных данных")
async def get_address_structure(
    municipality_id: int = Path(..., description="ID муниципального образования")
):
    """
    Определить структуру адресных данных для муниципального образования:
    - Есть ли улицы (городская структура)
    - Есть ли населенные пункты (сельская структура)
    - Есть ли дома напрямую
    """
    try:
        log_db_operation("get_address_structure", "as_addr_obj", {"municipality_id": municipality_id})
        
        async with AddressesService.get_connection() as connection:
            # Получаем информацию о муниципальном образовании
            municipality_query = """
            SELECT 
                ao.id,
                ao.objectid,
                ao.name,
                aot.shortname as type_name,
                ao.level
            FROM as_addr_obj ao
            JOIN as_addr_obj_types aot ON ao.level = aot.level
            WHERE ao.id = $1 
              AND ao.isactual = 1 
              AND ao.isactive = 1
            """
            
            municipality = await connection.fetchrow(municipality_query, municipality_id)
            if not municipality:
                raise HTTPException(status_code=404, detail="Муниципальное образование не найдено")
            
            # Подсчет улиц (уровень 8)
            streets_query = """
            SELECT COUNT(DISTINCT ao.id) as count
            FROM as_addr_obj ao
            WHERE ao.level = 8
              AND ao.isactual = 1 
              AND ao.isactive = 1
              AND EXISTS (
                  SELECT 1 FROM as_adm_hierarchy ah
                  WHERE ah.objectid = ao.objectid
                    AND ah.parentobjid = $1
              )
            """
            
            streets_result = await connection.fetchrow(streets_query, municipality['objectid'])
            streets_count = streets_result['count'] if streets_result else 0
            
            # Подсчет населенных пунктов (уровень 6, но не являющихся улицами)
            settlements_query = """
            SELECT COUNT(DISTINCT ao.id) as count
            FROM as_addr_obj ao
            JOIN as_addr_obj_types aot ON ao.level = aot.level
            WHERE ao.level = 6
              AND ao.isactual = 1 
              AND ao.isactive = 1
              AND aot.shortname NOT IN ('ул', 'пр-кт', 'пер', 'наб', 'ш', 'пл', 'б-р', 'тер')
              AND EXISTS (
                  SELECT 1 FROM as_adm_hierarchy ah
                  WHERE ah.objectid = ao.objectid
                    AND ah.parentobjid = $1
              )
            """
            
            settlements_result = await connection.fetchrow(settlements_query, municipality['objectid'])
            settlements_count = settlements_result['count'] if settlements_result else 0
            
            # Подсчет домов напрямую (без улицы)
            direct_houses_query = """
            SELECT COUNT(DISTINCT h.id) as count
            FROM as_houses h
            JOIN as_adm_hierarchy ah ON h.objectid = ah.objectid
            WHERE h.isactual = 1 
              AND h.isactive = 1
              AND ah.parentobjid = $1
            """
            
            direct_houses_result = await connection.fetchrow(direct_houses_query, municipality['objectid'])
            direct_houses_count = direct_houses_result['count'] if direct_houses_result else 0
            
            # Определение уровня и названия
            level_names = {
                1: "Субъект РФ",
                2: "Административный район", 
                3: "Муниципальный район",
                4: "Сельское поселение",
                5: "Город",
                6: "Населенный пункт",
                7: "Элемент планировочной структуры",
                8: "Элемент улично-дорожной сети"
            }
            
            level_name = level_names.get(municipality['level'], "Неизвестный уровень")
            
            # Формируем структуру
            address_structure = AddressStructure(
                id=municipality['id'],
                object_id=municipality['objectid'],
                name=municipality['name'],
                type_name=municipality['type_name'],
                level=municipality['level'],
                level_name=level_name,
                streets_count=streets_count,
                settlements_count=settlements_count,
                direct_houses_count=direct_houses_count,
                has_streets=(streets_count > 0),
                has_settlements=(settlements_count > 0)
            )
            
            logger.info(categorize_log(
                f"Структура для municipality_id={municipality_id}: улиц={streets_count}, поселений={settlements_count}, домов={direct_houses_count}", 
                LogCategory.SUCCESS
            ))
            
            return create_response(address_structure, "Структура адресных данных получена")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(categorize_log(f"Ошибка получения структуры адресных данных: {e}", LogCategory.ERROR))
        raise HTTPException(status_code=500, detail=f"Ошибка получения структуры адресных данных: {str(e)}")
