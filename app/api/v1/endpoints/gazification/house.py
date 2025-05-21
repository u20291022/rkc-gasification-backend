from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import HouseListResponse
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError
from tortoise.expressions import Q

router = APIRouter()

@router.get("/mo/{mo_id}/district/{district}/street/{street}/house", response_model=BaseResponse[HouseListResponse])
async def get_houses(mo_id: int = Path(), district: str = Path(), street: str = Path()):
    """Получение списка домов по ID муниципалитета, району и улице"""
    try:
        # Находим адреса, которые газифицированы (id_type_address = 3)
        gazified_addresses = await GazificationData.filter(
            id_type_address=3
        ).values_list('id_address', flat=True)
        
        # Получаем адреса, соответствующие району (district или city) и улице
        # исключая газифицированные адреса
        addresses = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(street=street) &
            Q(house__isnull=False) &
            ~Q(id__in=gazified_addresses)
        ).filter(
            district=district
        ).all()
        
        # Также проверяем записи, где district пустой, но city соответствует district
        # исключая газифицированные адреса
        additional_addresses = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(district__isnull=True) &
            Q(city=district) &
            Q(street=street) &
            Q(house__isnull=False) &
            ~Q(id__in=gazified_addresses)
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
