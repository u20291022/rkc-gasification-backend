from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import FlatListResponse
from app.models.models import AddressV2
from app.core.exceptions import DatabaseError

router = APIRouter()

@router.get("/mo/{mo_id}/district/{district}/street/{street}/house/{house}/flat", response_model=BaseResponse[FlatListResponse])
async def get_flats(mo_id: int = Path(), district: str = Path(), street: str = Path(), house: str = Path()):
    """Получение списка квартир по ID муниципалитета, району, улице и дому"""
    try:
        # Получаем адреса по всем параметрам
        addresses = await AddressV2.filter(
            id_mo=mo_id,
            street=street,
            house=house
        ).filter(
            district=district
        ).all()
        
        # Также проверяем записи, где district пустой, но city соответствует district
        additional_addresses = await AddressV2.filter(
            id_mo=mo_id,
            district__isnull=True,
            city=district,
            street=street,
            house=house
        ).all()
        
        all_addresses = addresses + additional_addresses
        
        log_db_operation("read", "AddressV2", {
            "mo_id": mo_id, 
            "district": district,
            "street": street,
            "house": house,
            "count": len(all_addresses)
        })
        
        # Собираем все уникальные квартиры
        flats = set()
        for address in all_addresses:
            if address.flat:
                flats.add(address.flat)
        
        return create_response(
            data=FlatListResponse(flats=sorted(list(flats)))
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка квартир: {str(e)}")
