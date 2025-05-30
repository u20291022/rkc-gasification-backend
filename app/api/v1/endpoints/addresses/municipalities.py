from fastapi import APIRouter, HTTPException, Query
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.addresses import (
    Municipality, AddressSearchResponse, MunicipalityListResponse
)
from app.core.addresses_service import AddressesService
from app.core.exceptions import DatabaseError
from app.core.logging import get_logger, categorize_log, LogCategory
from typing import Optional, List, Dict, Any

router = APIRouter()
logger = get_logger("addresses_municipalities")

@router.get("/municipalities", response_model=BaseResponse[AddressSearchResponse], 
           summary="Получить муниципальные образования")
async def get_municipalities(
    search: Optional[str] = Query(None, description="Поиск по названию"),
    limit: int = Query(50, ge=1, le=1000, description="Лимит результатов"),
    offset: int = Query(0, ge=0, description="Смещение")
):
    """
    Получить список муниципальных образований с возможностью поиска по названию
    Муниципальные образования - это объекты с уровнями 2,3,5,6 (районы, города, населенные пункты)
    
    Группирует схожие административные единицы:
    - город + городской округ (г + г.о.)
    - район + муниципальное образование (р-н + м.о./мкр)
    """
    try:
        log_db_operation("get_municipalities", "as_addr_obj", {"search": search, "limit": limit, "offset": offset})
        
        async with AddressesService.get_connection() as connection:
            # Базовый запрос для муниципальных образований с группировкой похожих объектов
            base_query = """
            WITH grouped_municipalities AS (
                SELECT 
                    ao.id,
                    ao.objectid,
                    ao.name,
                    aot.shortname as type_name,
                    aot.name as type_full_name,
                    ao.level,
                    CASE 
                        WHEN ao.level = 2 THEN ao.name || ' ' || aot.shortname
                        WHEN ao.level = 3 THEN ao.name || ' ' || aot.shortname  
                        WHEN ao.level = 5 THEN ao.name || ' ' || aot.shortname
                        WHEN ao.level = 6 THEN ao.name || ' ' || aot.shortname
                        ELSE ao.name
                    END as display_name,
                    -- Группируем похожие объекты (г. + г.о., р-н + м.о.)
                    CASE 
                        WHEN aot.shortname IN ('г', 'г.о.') THEN 
                            LOWER(TRIM(REGEXP_REPLACE(ao.name, '[^а-яё ]', '', 'gi')))
                        WHEN aot.shortname IN ('р-н', 'м.о.', 'мкр') THEN 
                            LOWER(TRIM(REGEXP_REPLACE(ao.name, '[^а-яё ]', '', 'gi')))
                        ELSE LOWER(TRIM(ao.name))
                    END as group_key
                FROM as_addr_obj ao
                JOIN as_addr_obj_types aot ON ao.level = aot.level
                WHERE ao.level IN (2, 3, 5, 6)
                  AND ao.isactual = 1 
                  AND ao.isactive = 1
                  AND aot.isactive = 1
                  {search_condition}
            ),
            municipality_groups AS (
                SELECT 
                    group_key,
                    MIN(id) as primary_id,
                    ARRAY_AGG(id ORDER BY 
                        CASE 
                            WHEN type_name IN ('г.о.', 'м.о.') THEN 1  -- Приоритет для округов
                            WHEN type_name = 'г' THEN 2  -- Затем города
                            WHEN type_name = 'р-н' THEN 3  -- Затем районы
                            ELSE 4
                        END, 
                        level DESC, 
                        id
                    ) as related_ids,
                    STRING_AGG(DISTINCT display_name, ' / ' ORDER BY display_name) as combined_name,
                    MIN(type_name ORDER BY 
                        CASE 
                            WHEN type_name IN ('г.о.', 'м.о.') THEN 1
                            WHEN type_name = 'г' THEN 2
                            WHEN type_name = 'р-н' THEN 3
                            ELSE 4
                        END
                    ) as primary_type_name,
                    MIN(type_full_name ORDER BY 
                        CASE 
                            WHEN type_name IN ('г.о.', 'м.о.') THEN 1
                            WHEN type_name = 'г' THEN 2
                            WHEN type_name = 'р-н' THEN 3
                            ELSE 4
                        END
                    ) as primary_type_full_name
                FROM grouped_municipalities
                GROUP BY group_key
            )
            SELECT 
                mg.primary_id as id,
                mg.combined_name as name,
                mg.primary_type_name as type_name,
                mg.primary_type_full_name as type_full_name,
                mg.related_ids
            FROM municipality_groups mg
            ORDER BY mg.combined_name
            LIMIT $1 OFFSET $2
            """
            
            # Условие поиска
            search_condition = ""
            params = [limit, offset]
            
            if search:
                search_condition = "AND LOWER(ao.name) LIKE LOWER($3)"
                params.append(f"%{search}%")
            
            query = base_query.format(search_condition=search_condition)
            
            # Выполняем запрос
            rows = await connection.fetch(query, *params)
            
            # Получаем общее количество
            count_query = """
            WITH grouped_municipalities AS (
                SELECT 
                    CASE 
                        WHEN aot.shortname IN ('г', 'г.о.') THEN 
                            LOWER(TRIM(REGEXP_REPLACE(ao.name, '[^а-яё ]', '', 'gi')))
                        WHEN aot.shortname IN ('р-н', 'м.о.', 'мкр') THEN 
                            LOWER(TRIM(REGEXP_REPLACE(ao.name, '[^а-яё ]', '', 'gi')))
                        ELSE LOWER(TRIM(ao.name))
                    END as group_key
                FROM as_addr_obj ao
                JOIN as_addr_obj_types aot ON ao.level = aot.level
                WHERE ao.level IN (2, 3, 5, 6)
                  AND ao.isactual = 1 
                  AND ao.isactive = 1
                  AND aot.isactive = 1
                  {search_condition}
            )
            SELECT COUNT(DISTINCT group_key) as total FROM grouped_municipalities
            """
            
            count_params = []
            if search:
                count_params.append(f"%{search}%")
            
            count_result = await connection.fetchrow(count_query.format(search_condition=search_condition), *count_params)
            total = count_result['total'] if count_result else 0
            
            # Формируем результат
            items = []
            for row in rows:
                municipality = {
                    "id": row['id'],
                    "name": row['name'],
                    "type_name": row['type_name'],
                    "type_full_name": row['type_full_name'],
                    "related_ids": list(row['related_ids']) if row['related_ids'] else []
                }
                items.append(municipality)
            
            result_data = AddressSearchResponse(total=total, items=items)
            
            logger.info(categorize_log(
                f"Найдено {total} муниципальных образований, возвращено {len(items)}", 
                LogCategory.SUCCESS
            ))
            
            return create_response(result_data, f"Найдено {total} муниципальных образований")
    
    except Exception as e:
        logger.error(categorize_log(f"Ошибка получения муниципальных образований: {e}", LogCategory.ERROR))
        raise HTTPException(status_code=500, detail=f"Ошибка получения муниципальных образований: {str(e)}")
