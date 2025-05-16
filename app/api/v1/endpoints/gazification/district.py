from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import DistrictListResponse
from app.models.models import AddressV2
from app.core.exceptions import DatabaseError

router = APIRouter()

@router.get("/mo/{mo_id}/district", response_model=BaseResponse[DistrictListResponse])
async def get_districts(mo_id: int = Path()):
    """Получение списка районов по ID муниципалитета"""
    try:
        # Получаем уникальные районы для данного муниципалитета
        addresses = await AddressV2.filter(id_mo=mo_id).all()
        
        log_db_operation("read", "AddressV2", {"mo_id": mo_id, "count": len(addresses)})
        
        # Собираем все уникальные районы
        districts = set()
        for address in addresses:
            # Используем district или city, если district отсутствует
            district_name = address.district or address.city
            if district_name:
                districts.add(district_name)
        
        return create_response(
            data=DistrictListResponse(districts=sorted(list(districts)))
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка районов: {str(e)}")
