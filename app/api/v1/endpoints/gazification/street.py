from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import StreetListResponse
from app.models.models import AddressV2
from app.core.exceptions import DatabaseError
from tortoise.functions import Lower
from tortoise.functions import Trim

router = APIRouter()

@router.get("/mo/{mo_id}/district/{district}/street", response_model=BaseResponse[StreetListResponse])
async def get_streets(mo_id: int = Path(), district: str = Path()):
    """Получение списка улиц по ID муниципалитета и ID района"""
    try:
        # Предварительно обрабатываем district в Python (удаляем пробелы и приводим к нижнему регистру)
        normalized_district = district.strip().lower()
        
        # Получаем уникальные улицы для данного муниципалитета и района
        # Используем Lower и Trim для сравнения в БД без учета регистра и пробелов
        addresses = await AddressV2.filter(
            id_mo=mo_id
        ).annotate(
            district_lower=Lower(Trim("district"))
        ).filter(
            district_lower=normalized_district
        ).all()
        
        # Также проверяем записи, где district пустой, но city соответствует district_id
        additional_addresses = await AddressV2.filter(
            id_mo=mo_id,
            district__isnull=True
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