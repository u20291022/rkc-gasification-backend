from fastapi import APIRouter, HTTPException, Query
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.addresses import AddressSearchResponse, RuralHouse, RuralHouseListResponse
from app.core.addresses_service import AddressesService
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger, categorize_log, LogCategory
from typing import Optional

router = APIRouter()
logger = get_logger("addresses_rural_houses")

@router.get("/rural-houses", response_model=BaseResponse[AddressSearchResponse], 
           summary="Получить дома в населенном пункте")
async def get_rural_houses(
    settlement_id: int = Query(..., description="Object ID населенного пункта"),
    search: Optional[str] = Query(None, description="Поиск по номеру дома"),
    limit: int = Query(50, ge=1, le=1000, description="Лимит результатов"),
    offset: int = Query(0, ge=0, description="Смещение")
):
    """
    Получить список домов в населенном пункте (сельская местность, без привязки к улице)
    """
    try:
        log_db_operation("get_rural_houses", "as_houses", {
            "settlement_id": settlement_id, 
            "search": search, 
            "limit": limit, 
            "offset": offset
        })
        
        async with AddressesService.get_connection() as connection:
            # Запрос для получения сельских домов
            base_query = """
            SELECT DISTINCT
                h.id,
                h.objectid,
                h.housenum,
                h.addnum1,
                h.addnum2,
                COALESCE(
                    CASE 
                        WHEN ht.shortname IS NOT NULL AND h.housenum IS NOT NULL 
                        THEN ht.shortname || ' ' || h.housenum
                        WHEN h.housenum IS NOT NULL 
                        THEN h.housenum
                        ELSE 'Без номера'
                    END ||
                    CASE 
                        WHEN at1.shortname IS NOT NULL AND h.addnum1 IS NOT NULL 
                        THEN ' ' || at1.shortname || ' ' || h.addnum1
                        WHEN h.addnum1 IS NOT NULL 
                        THEN ' ' || h.addnum1
                        ELSE ''
                    END ||
                    CASE 
                        WHEN at2.shortname IS NOT NULL AND h.addnum2 IS NOT NULL 
                        THEN ' ' || at2.shortname || ' ' || h.addnum2
                        WHEN h.addnum2 IS NOT NULL 
                        THEN ' ' || h.addnum2
                        ELSE ''
                    END,
                    'Без номера'
                ) as full_address,
                ht.shortname as house_type_name,
                ao.name as settlement_name,
                aot.shortname as settlement_type
            FROM as_houses h
            LEFT JOIN as_house_types ht ON h.housetype = ht.id
            LEFT JOIN as_addhouse_types at1 ON h.addtype1 = at1.id  
            LEFT JOIN as_addhouse_types at2 ON h.addtype2 = at2.id
            JOIN as_adm_hierarchy ah ON h.objectid = ah.objectid
            JOIN as_addr_obj ao ON ao.objectid = $1
            JOIN as_addr_obj_types aot ON ao.level = aot.level
            WHERE h.isactual = 1 
              AND h.isactive = 1
              AND ah.parentobjid = $1
              {search_condition}
            ORDER BY 
                CAST(NULLIF(REGEXP_REPLACE(h.housenum, '[^0-9]', '', 'g'), '') AS INTEGER) NULLS LAST,
                h.housenum,
                h.addnum1,
                h.addnum2
            LIMIT $2 OFFSET $3
            """
            
            # Условие поиска и параметры
            search_condition = ""
            params = [settlement_id, limit, offset]
            
            if search:
                search_condition = """
                AND (
                    LOWER(h.housenum) LIKE LOWER($4) OR
                    LOWER(h.addnum1) LIKE LOWER($4) OR
                    LOWER(h.addnum2) LIKE LOWER($4)
                )
                """
                params.append(f"%{search}%")
            
            query = base_query.format(search_condition=search_condition)
            
            # Выполняем запрос
            rows = await connection.fetch(query, *params)
            
            # Получаем общее количество
            count_query = """
            SELECT COUNT(DISTINCT h.id) as total
            FROM as_houses h
            JOIN as_adm_hierarchy ah ON h.objectid = ah.objectid
            WHERE h.isactual = 1 
              AND h.isactive = 1
              AND ah.parentobjid = $1
              {search_condition}
            """
            
            count_params = [settlement_id]
            if search:
                count_params.append(f"%{search}%")
            
            count_result = await connection.fetchrow(count_query.format(search_condition=search_condition), *count_params)
            total = count_result['total'] if count_result else 0
            
            # Формируем результат
            items = []
            for row in rows:
                rural_house = {
                    "id": row['id'],
                    "object_id": row['objectid'],
                    "house_num": row['housenum'],
                    "add_num1": row['addnum1'],
                    "add_num2": row['addnum2'],
                    "full_address": row['full_address'],
                    "house_type_name": row['house_type_name'],
                    "settlement_name": row['settlement_name'],
                    "settlement_type": row['settlement_type']
                }
                items.append(rural_house)
            
            result_data = AddressSearchResponse(total=total, items=items)
            
            logger.info(categorize_log(
                f"Найдено {total} сельских домов для settlement_id={settlement_id}, возвращено {len(items)}", 
                LogCategory.SUCCESS
            ))
            
            return create_response(result_data, f"Найдено {total} домов")
    
    except Exception as e:
        logger.error(categorize_log(f"Ошибка получения сельских домов: {e}", LogCategory.ERROR))
        raise HTTPException(status_code=500, detail=f"Ошибка получения сельских домов: {str(e)}")
