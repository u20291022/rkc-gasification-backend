from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import StreetListResponse
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError
from tortoise.functions import Lower, Trim
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
          # Оптимизированный запрос: получаем уникальные улицы напрямую из БД
        # для записей с district, соответствующим переданному значению
        district_streets = await AddressV2.filter(
            Q(id_mo=mo_id) & 
            Q(house__isnull=False) & 
            ~Q(id__in=gazified_addresses)
        ).annotate(
            district_lower=Lower(Trim("district"))
        ).filter(
            Q(district_lower=normalized_district) &
            Q(street__isnull=False)
        ).distinct().values_list(
            'street', flat=True)
          # Также получаем улицы для записей, где district пустой, но city соответствует district
        city_streets = await AddressV2.filter(
            Q(id_mo=mo_id) & 
            Q(district__isnull=True) & 
            Q(house__isnull=False) & 
            ~Q(id__in=gazified_addresses)
        ).annotate(
            city_lower=Lower(Trim("city"))
        ).filter(
            Q(city_lower=normalized_district) &
            Q(street__isnull=False)
        ).distinct().values_list(
            'street', flat=True)
        
        # Объединяем результаты
        all_streets = list(set(list(district_streets) + list(city_streets)))
        
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