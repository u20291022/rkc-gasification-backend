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
        
        # Получаем уникальные улицы для данного муниципалитета и района,
        # исключая газифицированные адреса и обеспечивая наличие дома
        addresses = await AddressV2.filter(
            Q(id_mo=mo_id) & 
            Q(house__isnull=False) & 
            ~Q(id__in=gazified_addresses)
        ).annotate(
            district_lower=Lower(Trim("district"))
        ).filter(
            district_lower=normalized_district
        ).all()
        
        # Также проверяем записи, где district пустой, но city соответствует district_id,
        # исключая газифицированные адреса и обеспечивая наличие дома
        additional_addresses = await AddressV2.filter(
            Q(id_mo=mo_id) & 
            Q(district__isnull=True) & 
            Q(house__isnull=False) & 
            ~Q(id__in=gazified_addresses)
        ).annotate(
            city_lower=Lower(Trim("city"))
        ).filter(
            city_lower=normalized_district
        ).all()
        
        # Объединяем результаты
        all_addresses = addresses + additional_addresses
        
        log_db_operation("read", "AddressV2", {
            "mo_id": mo_id, 
            "district": district, 
            "normalized_district": normalized_district,
            "count": len(all_addresses)
        })
        
        # Собираем все уникальные улицы
        streets = set()
        for address in all_addresses:
            if address.street:
                streets.add(address.street)
        
        return create_response(
            data=StreetListResponse(streets=sorted(list(streets)))
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка улиц: {str(e)}")