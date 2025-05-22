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
          # Оптимизированный запрос: получаем уникальные квартиры напрямую из БД
        # для записей с district, соответствующим переданному значению
        district_flats = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(street=street) &
            Q(house=house) &
            Q(district=district) &
            Q(flat__isnull=False) &
            ~Q(id__in=gazified_addresses)
        ).distinct().values_list(
            'flat', flat=True)
          # Также получаем квартиры для записей, где district пустой, но city соответствует district
        city_flats = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(district__isnull=True) &
            Q(city=district) &
            Q(street=street) &
            Q(house=house) &
            Q(flat__isnull=False) &
            ~Q(id__in=gazified_addresses)
        ).distinct().values_list(
            'flat', flat=True)
        
        # Объединяем результаты
        all_flats = list(set(list(district_flats) + list(city_flats)))
        
        log_db_operation("read", "AddressV2", {
            "mo_id": mo_id, 
            "district": district,
            "street": street,
            "house": house,
            "count": len(all_flats)
        })
        
        return create_response(
            data=FlatListResponse(flats=sorted(all_flats))
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка квартир: {str(e)}")
