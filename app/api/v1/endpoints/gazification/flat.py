from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import FlatListResponse
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError
from tortoise.expressions import Q

router = APIRouter()

@router.get("/mo/{mo_id}/district/{district}/street/{street}/house/{house}/flat", response_model=BaseResponse[FlatListResponse])
async def get_flats(mo_id: int = Path(), district: str = Path(), street: str = Path(), house: str = Path()):
    """Получение списка квартир по ID муниципалитета, району, улице и дому"""
    try:
        # Находим адреса, которые газифицированы (id_type_address = 3)
        gazified_addresses = await GazificationData.filter(
            id_type_address=3
        ).values_list('id_address', flat=True)
        
        # Получаем адреса по всем параметрам, исключая газифицированные
        addresses = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(street=street) &
            Q(house=house) &
            Q(flat__isnull=False) &
            ~Q(id__in=gazified_addresses)
        ).filter(
            district=district
        ).all()
        
        # Также проверяем записи, где district пустой, но city соответствует district
        # исключая газифицированные
        additional_addresses = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(district__isnull=True) &
            Q(city=district) &
            Q(street=street) &
            Q(house=house) &
            Q(flat__isnull=False) &
            ~Q(id__in=gazified_addresses)
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
