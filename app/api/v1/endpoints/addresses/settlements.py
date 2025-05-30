from fastapi import APIRouter, HTTPException, Query
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.addresses import AddressSearchResponse, Settlement, SettlementListResponse
from app.core.addresses_service import AddressesService
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger, categorize_log, LogCategory
from typing import Optional

router = APIRouter()
logger = get_logger("addresses_settlements")

@router.get("/settlements", response_model=BaseResponse[AddressSearchResponse], 
           summary="Получить населенные пункты")
async def get_settlements(
    municipality_id: int = Query(..., description="ID административной единицы (района, г.о., м.о.)"),
    search: Optional[str] = Query(None, description="Поиск по названию населенного пункта"),
    limit: int = Query(50, ge=1, le=1000, description="Лимит результатов"),
    offset: int = Query(0, ge=0, description="Смещение")
):
    """
    Получить список населенных пунктов (деревни, села, СНТ и т.д.) 
    для заданной административной единицы
    """
    try:
        log_db_operation("get_settlements", "as_addr_obj", {
            "municipality_id": municipality_id, 
            "search": search, 
            "limit": limit, 
            "offset": offset
        })
        
        async with AddressesService.get_connection() as connection:
            # Запрос для получения населенных пунктов
            base_query = """
            SELECT DISTINCT
                ao.id,
                ao.objectid,
                ao.name,
                aot.shortname as type_name,
                aot.name as type_full_name,
                (
                    SELECT COUNT(DISTINCT h.id)
                    FROM as_houses h
                    JOIN as_adm_hierarchy ah2 ON h.objectid = ah2.objectid
                    WHERE ah2.parentobjid = ao.objectid
                      AND h.isactual = 1 
                      AND h.isactive = 1
                ) as houses_count
            FROM as_addr_obj ao
            JOIN as_addr_obj_types aot ON ao.level = aot.level
            WHERE ao.level = 6  -- Населенные пункты
              AND ao.isactual = 1 
              AND ao.isactive = 1
              AND aot.isactive = 1
              AND aot.shortname NOT IN ('ул', 'пр-кт', 'пер', 'наб', 'ш', 'пл', 'б-р', 'тер')  -- Исключаем улицы
              AND EXISTS (
                  SELECT 1 FROM as_adm_hierarchy ah
                  WHERE ah.objectid = ao.objectid
                    AND ah.parentobjid = (
                        SELECT objectid FROM as_addr_obj 
                        WHERE id = $1 AND isactual = 1 AND isactive = 1
                    )
              )
              {search_condition}
            ORDER BY ao.name
            LIMIT $2 OFFSET $3
            """
            
            # Условие поиска и параметры
            search_condition = ""
            params = [municipality_id, limit, offset]
            
            if search:
                search_condition = "AND LOWER(ao.name) LIKE LOWER($4)"
                params.append(f"%{search}%")
            
            query = base_query.format(search_condition=search_condition)
            
            # Выполняем запрос
            rows = await connection.fetch(query, *params)
            
            # Получаем общее количество
            count_query = """
            SELECT COUNT(DISTINCT ao.id) as total
            FROM as_addr_obj ao
            JOIN as_addr_obj_types aot ON ao.level = aot.level
            WHERE ao.level = 6
              AND ao.isactual = 1 
              AND ao.isactive = 1
              AND aot.isactive = 1
              AND aot.shortname NOT IN ('ул', 'пр-кт', 'пер', 'наб', 'ш', 'пл', 'б-р', 'тер')
              AND EXISTS (
                  SELECT 1 FROM as_adm_hierarchy ah
                  WHERE ah.objectid = ao.objectid
                    AND ah.parentobjid = (
                        SELECT objectid FROM as_addr_obj 
                        WHERE id = $1 AND isactual = 1 AND isactive = 1
                    )
              )
              {search_condition}
            """
            
            count_params = [municipality_id]
            if search:
                count_params.append(f"%{search}%")
            
            count_result = await connection.fetchrow(count_query.format(search_condition=search_condition), *count_params)
            total = count_result['total'] if count_result else 0
            
            # Формируем результат
            items = []
            for row in rows:
                settlement = {
                    "id": row['id'],
                    "object_id": row['objectid'],
                    "name": row['name'],
                    "type_name": row['type_name'],
                    "type_full_name": row['type_full_name'],
                    "houses_count": row['houses_count'] or 0
                }
                items.append(settlement)
            
            result_data = AddressSearchResponse(total=total, items=items)
            
            logger.info(categorize_log(
                f"Найдено {total} населенных пунктов для municipality_id={municipality_id}, возвращено {len(items)}", 
                LogCategory.SUCCESS
            ))
            
            return create_response(result_data, f"Найдено {total} населенных пунктов")
    
    except Exception as e:
        logger.error(categorize_log(f"Ошибка получения населенных пунктов: {e}", LogCategory.ERROR))
        raise HTTPException(status_code=500, detail=f"Ошибка получения населенных пунктов: {str(e)}")
