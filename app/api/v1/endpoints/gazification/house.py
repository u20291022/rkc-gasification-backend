from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import HouseListResponse
from app.models.models import AddressV2
from app.core.exceptions import DatabaseError

router = APIRouter()

@router.get("/mo/{mo_id}/district/{district}/street/{street}/house", response_model=BaseResponse[HouseListResponse])
async def get_houses(mo_id: int = Path(), district: str = Path(), street: str = Path()):
    """Получение списка домов по ID муниципалитета, району и улице"""
    try:
        # Получаем адреса, соответствующие району (district или city) и улице
        addresses = await AddressV2.filter(
            id_mo=mo_id,
            street=street
        ).filter(
            district=district
        ).all()
        
        # Также проверяем записи, где district пустой, но city соответствует district
        additional_addresses = await AddressV2.filter(
            id_mo=mo_id,
            district__isnull=True,
            city=district,
            street=street
        ).all()
        
        all_addresses = addresses + additional_addresses
        
        log_db_operation("read", "AddressV2", {
            "mo_id": mo_id, 
            "district": district,
            "street": street,
            "count": len(all_addresses)
        })
        
        # Собираем все уникальные дома
        houses = set()
        for address in all_addresses:
            if address.house:
                houses.add(address.house)
        
        return create_response(
            data=HouseListResponse(houses=sorted(list(houses)))
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка домов: {str(e)}")
