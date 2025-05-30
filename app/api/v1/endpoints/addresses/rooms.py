from fastapi import APIRouter, HTTPException, Query
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.addresses import AddressSearchResponse, Room, RoomListResponse
from app.core.addresses_service import AddressesService
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger, categorize_log, LogCategory
from typing import Optional

router = APIRouter()
logger = get_logger("addresses_rooms")

@router.get("/rooms", response_model=BaseResponse[AddressSearchResponse], 
           summary="Получить комнаты")
async def get_rooms(
    apartment_id: int = Query(..., description="ID квартиры"),
    search: Optional[str] = Query(None, description="Поиск по номеру комнаты"),
    limit: int = Query(50, ge=1, le=1000, description="Лимит результатов"),
    offset: int = Query(0, ge=0, description="Смещение")
):
    """
    Получить список комнат для заданной квартиры
    """
    try:
        log_db_operation("get_rooms", "as_rooms", {
            "apartment_id": apartment_id, 
            "search": search, 
            "limit": limit, 
            "offset": offset
        })
        
        async with AddressesService.get_connection() as connection:
            # Запрос для получения комнат
            base_query = """
            SELECT DISTINCT
                r.id,
                r.number,
                rt.shortname as room_type,
                $1 as apartment_id,
                ap.number as apartment_number,
                COALESCE(
                    CASE 
                        WHEN h.housetype IS NOT NULL AND h.housenum IS NOT NULL 
                        THEN ht.shortname || ' ' || h.housenum
                        ELSE h.housenum
                    END,
                    'Без номера'
                ) as house_number
            FROM as_rooms r
            LEFT JOIN as_room_types rt ON r.roomtype = rt.id
            JOIN as_adm_hierarchy ah ON r.objectid = ah.objectid
            JOIN as_apartments ap ON ap.id = $1
            JOIN as_adm_hierarchy ah2 ON ap.objectid = ah2.objectid
            JOIN as_houses h ON h.objectid = ah2.parentobjid
            LEFT JOIN as_house_types ht ON h.housetype = ht.id
            WHERE r.isactual = 1 
              AND r.isactive = 1
              AND ah.parentobjid = ap.objectid
              {search_condition}
            ORDER BY 
                CAST(NULLIF(REGEXP_REPLACE(r.number, '[^0-9]', '', 'g'), '') AS INTEGER) NULLS LAST,
                r.number
            LIMIT $2 OFFSET $3
            """
            
            # Условие поиска и параметры
            search_condition = ""
            params = [apartment_id, limit, offset]
            
            if search:
                search_condition = "AND LOWER(r.number) LIKE LOWER($4)"
                params.append(f"%{search}%")
            
            query = base_query.format(search_condition=search_condition)
            
            # Выполняем запрос
            rows = await connection.fetch(query, *params)
            
            # Получаем общее количество
            count_query = """
            SELECT COUNT(DISTINCT r.id) as total
            FROM as_rooms r
            JOIN as_adm_hierarchy ah ON r.objectid = ah.objectid
            JOIN as_apartments ap ON ap.id = $1
            WHERE r.isactual = 1 
              AND r.isactive = 1
              AND ah.parentobjid = ap.objectid
              {search_condition}
            """
            
            count_params = [apartment_id]
            if search:
                count_params.append(f"%{search}%")
            
            count_result = await connection.fetchrow(count_query.format(search_condition=search_condition), *count_params)
            total = count_result['total'] if count_result else 0
            
            # Формируем результат
            items = []
            for row in rows:
                room = {
                    "id": row['id'],
                    "number": row['number'],
                    "room_type": row['room_type'],
                    "apartment_id": row['apartment_id'],
                    "apartment_number": row['apartment_number'],
                    "house_number": row['house_number']
                }
                items.append(room)
            
            result_data = AddressSearchResponse(total=total, items=items)
            
            logger.info(categorize_log(
                f"Найдено {total} комнат для apartment_id={apartment_id}, возвращено {len(items)}", 
                LogCategory.SUCCESS
            ))
            
            return create_response(result_data, f"Найдено {total} комнат")
    
    except Exception as e:
        logger.error(categorize_log(f"Ошибка получения комнат: {e}", LogCategory.ERROR))
        raise HTTPException(status_code=500, detail=f"Ошибка получения комнат: {str(e)}")
