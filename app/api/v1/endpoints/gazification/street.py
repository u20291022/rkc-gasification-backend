from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import StreetListResponse
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError
from tortoise.expressions import Q

router = APIRouter()

@router.get("/mo/{mo_id}/district/{district}/street", response_model=BaseResponse[StreetListResponse])
async def get_streets(mo_id: int = Path(), district: str = Path()):
    """Получение списка улиц по ID муниципалитета и ID района"""
    try:
        # Предварительно обрабатываем district в Python (удаляем пробелы и приводим к нижнему регистру)
        normalized_district = district.strip().lower()
        
        # Находим адреса, которые газифицированы (id_type_address = 3)
        gazified_addresses = await GazificationData.filter(
            id_type_address=3
        ).values_list('id_address', flat=True)
          # Получаем улицы для записей с district, соответствующим переданному значению
        district_streets = await AddressV2.filter(
            Q(id_mo=mo_id) & 
            Q(house__isnull=False) & 
            Q(district__isnull=False) &
            ~Q(district='') &
            Q(street__isnull=False) &
            ~Q(street='') &
            ~Q(id__in=gazified_addresses)
        ).distinct().values_list('street', 'district', flat=False)
        
        # Также получаем улицы для записей, где district пустой, но city соответствует district
        city_streets = await AddressV2.filter(
            Q(id_mo=mo_id) & 
            Q(district__isnull=True) & 
            Q(city__isnull=False) &
            ~Q(city='') &
            Q(house__isnull=False) & 
            Q(street__isnull=False) &
            ~Q(street='') &
            ~Q(id__in=gazified_addresses)
        ).distinct().values_list('street', 'city', flat=False)
        
        # Фильтруем результаты на Python
        filtered_streets = []
        
        # Обрабатываем улицы из поля district
        for street, district_name in district_streets:
            if (street and street.strip() and 
                district_name and district_name.strip().lower() == normalized_district):
                filtered_streets.append(street.strip())
        
        # Обрабатываем улицы из поля city
        for street, city_name in city_streets:
            if (street and street.strip() and 
                city_name and city_name.strip().lower() == normalized_district):
                filtered_streets.append(street.strip())
        
        # Убираем дубликаты
        all_streets = list(set(filtered_streets))
        
        if not all_streets:
            all_streets.append('Нет улиц')

        log_db_operation("read", "AddressV2", {
            "mo_id": mo_id, 
            "district": district, 
            "normalized_district": normalized_district,
            "count": len(all_streets)
        })
        
        return create_response(
            data=StreetListResponse(streets=sorted(all_streets))
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка улиц: {str(e)}")