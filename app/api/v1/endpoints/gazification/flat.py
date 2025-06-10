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
        
        # Получаем квартиры для записей с district, соответствующим переданному значению
        district_flats = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(street=street) &
            Q(house=house) &
            Q(district__isnull=False) &
            ~Q(district__exact='') &
            Q(flat__isnull=False) &
            ~Q(flat__exact='') &
            ~Q(id__in=gazified_addresses)
        ).distinct().values_list('flat', 'district', flat=False)
        
        # Также получаем квартиры для записей, где district пустой, но city соответствует district
        city_flats = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(district__isnull=True) &
            Q(city__isnull=False) &
            ~Q(city__exact='') &
            Q(street=street) &
            Q(house=house) &
            Q(flat__isnull=False) &
            ~Q(flat__exact='') &
            ~Q(id__in=gazified_addresses)
        ).distinct().values_list('flat', 'city', flat=False)
        
        # Фильтруем результаты на Python
        filtered_flats = []
        
        # Обрабатываем квартиры из записей с district
        for flat, district_name in district_flats:
            if (flat and flat.strip() and 
                district_name and district_name.strip() == district):
                filtered_flats.append(flat.strip())
        
        # Обрабатываем квартиры из записей с city
        for flat, city_name in city_flats:
            if (flat and flat.strip() and 
                city_name and city_name.strip() == district):
                filtered_flats.append(flat.strip())
        
        # Убираем дубликаты
        all_flats = list(set(filtered_flats))
        
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
