from fastapi import APIRouter, HTTPException, Query
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.addresses import AddressSearchResponse, House, HouseListResponse
from app.core.addresses_service import AddressesService, build_full_house_number
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger, categorize_log, LogCategory
from typing import Optional

router = APIRouter()
logger = get_logger("addresses_houses")

@router.get("/houses", response_model=BaseResponse[AddressSearchResponse], 
           summary="Получить дома")
async def get_houses(
    street_id: int = Query(..., description="ID улицы"),
    search: Optional[str] = Query(None, description="Поиск по номеру дома"),
    limit: int = Query(50, ge=1, le=1000, description="Лимит результатов"),
    offset: int = Query(0, ge=0, description="Смещение")
):
    """
    Получить список домов для заданной улицы
    """
    try:
        log_db_operation("get_houses", "as_houses", {
            "street_id": street_id, 
            "search": search, 
            "limit": limit, 
            "offset": offset
        })
        
        async with AddressesService.get_connection() as connection:
            # Запрос для получения домов
            base_query = """
            SELECT DISTINCT
                h.id,
                h.housenum,
                h.addnum1,
                h.addnum2,
                ht.shortname as house_type,
                at1.shortname as add_type1,
                at2.shortname as add_type2,
                $1 as street_id,
                ao.name as street_name,
                (SELECT id FROM as_addr_obj WHERE objectid = ah.parentobjid AND level IN (2,3,5,6) AND isactual = 1 AND isactive = 1 LIMIT 1) as municipality_id
            FROM as_houses h
            LEFT JOIN as_house_types ht ON h.housetype = ht.id
            LEFT JOIN as_addhouse_types at1 ON h.addtype1 = at1.id  
            LEFT JOIN as_addhouse_types at2 ON h.addtype2 = at2.id
            JOIN as_adm_hierarchy ah ON h.objectid = ah.objectid
            JOIN as_addr_obj ao ON ao.id = $1
            WHERE h.isactual = 1 
              AND h.isactive = 1
              AND ah.parentobjid = (
                  SELECT objectid FROM as_addr_obj 
                  WHERE id = $1 AND isactual = 1 AND isactive = 1
              )
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
            params = [street_id, limit, offset]
            
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
              AND ah.parentobjid = (
                  SELECT objectid FROM as_addr_obj 
                  WHERE id = $1 AND isactual = 1 AND isactive = 1
              )
              {search_condition}
            """
            
            count_params = [street_id]
            if search:
                count_params.append(f"%{search}%")
            
            count_result = await connection.fetchrow(count_query.format(search_condition=search_condition), *count_params)
            total = count_result['total'] if count_result else 0
            
            # Формируем результат
            items = []
            for row in rows:
                # Строим полный номер дома
                full_number = build_full_house_number(
                    row['housenum'] or "",
                    row['addnum1'] or "",
                    row['addnum2'] or "",
                    row['house_type'] or "",
                    row['add_type1'] or "",
                    row['add_type2'] or ""
                )
                
                house = {
                    "id": row['id'],
                    "house_num": row['housenum'],
                    "add_num1": row['addnum1'],
                    "add_num2": row['addnum2'],
                    "house_type": row['house_type'],
                    "add_type1": row['add_type1'],
                    "add_type2": row['add_type2'],
                    "full_number": full_number,
                    "street_id": row['street_id'],
                    "street_name": row['street_name'],
                    "municipality_id": row['municipality_id']
                }
                items.append(house)
            
            result_data = AddressSearchResponse(total=total, items=items)
            
            logger.info(categorize_log(
                f"Найдено {total} домов для street_id={street_id}, возвращено {len(items)}", 
                LogCategory.SUCCESS
            ))
            
            return create_response(result_data, f"Найдено {total} домов")
    
    except Exception as e:
        logger.error(categorize_log(f"Ошибка получения домов: {e}", LogCategory.ERROR))
        raise HTTPException(status_code=500, detail=f"Ошибка получения домов: {str(e)}")
