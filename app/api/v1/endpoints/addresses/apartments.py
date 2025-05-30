from fastapi import APIRouter, HTTPException, Query
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.addresses import AddressSearchResponse, Apartment, ApartmentListResponse
from app.core.addresses_service import AddressesService
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger, categorize_log, LogCategory
from typing import Optional

router = APIRouter()
logger = get_logger("addresses_apartments")

@router.get("/apartments", response_model=BaseResponse[AddressSearchResponse], 
           summary="Получить квартиры")
async def get_apartments(
    house_id: int = Query(..., description="ID дома"),
    search: Optional[str] = Query(None, description="Поиск по номеру квартиры"),
    limit: int = Query(50, ge=1, le=1000, description="Лимит результатов"),
    offset: int = Query(0, ge=0, description="Смещение")
):
    """
    Получить список квартир/помещений для заданного дома
    """
    try:
        log_db_operation("get_apartments", "as_apartments", {
            "house_id": house_id, 
            "search": search, 
            "limit": limit, 
            "offset": offset
        })
        
        async with AddressesService.get_connection() as connection:
            # Запрос для получения квартир
            base_query = """
            SELECT DISTINCT
                ap.id,
                ap.number,
                apt.shortname as apart_type,
                $1 as house_id,
                COALESCE(
                    CASE 
                        WHEN h.housetype IS NOT NULL AND h.housenum IS NOT NULL 
                        THEN ht.shortname || ' ' || h.housenum
                        ELSE h.housenum
                    END,
                    'Без номера'
                ) as house_number,
                ao.name as street_name
            FROM as_apartments ap
            LEFT JOIN as_apartment_types apt ON ap.aparttype = apt.id
            JOIN as_adm_hierarchy ah ON ap.objectid = ah.objectid
            JOIN as_houses h ON h.id = $1
            LEFT JOIN as_house_types ht ON h.housetype = ht.id
            JOIN as_adm_hierarchy ah2 ON h.objectid = ah2.objectid
            JOIN as_addr_obj ao ON ao.objectid = ah2.parentobjid AND ao.level = 8
            WHERE ap.isactual = 1 
              AND ap.isactive = 1
              AND ah.parentobjid = h.objectid
              {search_condition}
            ORDER BY 
                CAST(NULLIF(REGEXP_REPLACE(ap.number, '[^0-9]', '', 'g'), '') AS INTEGER) NULLS LAST,
                ap.number
            LIMIT $2 OFFSET $3
            """
            
            # Условие поиска и параметры
            search_condition = ""
            params = [house_id, limit, offset]
            
            if search:
                search_condition = "AND LOWER(ap.number) LIKE LOWER($4)"
                params.append(f"%{search}%")
            
            query = base_query.format(search_condition=search_condition)
            
            # Выполняем запрос
            rows = await connection.fetch(query, *params)
            
            # Получаем общее количество
            count_query = """
            SELECT COUNT(DISTINCT ap.id) as total
            FROM as_apartments ap
            JOIN as_adm_hierarchy ah ON ap.objectid = ah.objectid
            JOIN as_houses h ON h.id = $1
            WHERE ap.isactual = 1 
              AND ap.isactive = 1
              AND ah.parentobjid = h.objectid
              {search_condition}
            """
            
            count_params = [house_id]
            if search:
                count_params.append(f"%{search}%")
            
            count_result = await connection.fetchrow(count_query.format(search_condition=search_condition), *count_params)
            total = count_result['total'] if count_result else 0
            
            # Формируем результат
            items = []
            for row in rows:
                apartment = {
                    "id": row['id'],
                    "number": row['number'],
                    "apart_type": row['apart_type'],
                    "house_id": row['house_id'],
                    "house_number": row['house_number'],
                    "street_name": row['street_name']
                }
                items.append(apartment)
            
            result_data = AddressSearchResponse(total=total, items=items)
            
            logger.info(categorize_log(
                f"Найдено {total} квартир для house_id={house_id}, возвращено {len(items)}", 
                LogCategory.SUCCESS
            ))
            
            return create_response(result_data, f"Найдено {total} квартир")
    
    except Exception as e:
        logger.error(categorize_log(f"Ошибка получения квартир: {e}", LogCategory.ERROR))
        raise HTTPException(status_code=500, detail=f"Ошибка получения квартир: {str(e)}")
