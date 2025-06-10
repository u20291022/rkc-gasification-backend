from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import HouseListResponse
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError
from tortoise.expressions import Q
from tortoise.functions import Trim

router = APIRouter()

@router.get("/mo/{mo_id}/district/{district}/street/{street}/house", response_model=BaseResponse[HouseListResponse])
async def get_houses(mo_id: int = Path(), district: str = Path(), street: str = Path()):
    """Получение списка домов по ID муниципалитета, району и улице"""
    try:
        # Находим адреса, которые газифицированы (id_type_address = 3)
        gazified_addresses = await GazificationData.filter(
            id_type_address=3
        ).values_list('id_address', flat=True)
          
        # Создаем условие для проверки улицы
        street_condition = Q(street=street)
        if street == '' or street == 'Нет улиц':
            # Если улица пустая строка, добавляем проверку на NULL
            street_condition = Q(street='') | Q(street__isnull=True)
            # Оптимизированный запрос: получаем уникальные дома напрямую из БД
        # для записей с district, соответствующим переданному значению
        district_houses = await AddressV2.filter(
            Q(id_mo=mo_id) &
            street_condition &
            Q(house__isnull=False) &
            ~Q(house__exact='') &  # Исключаем пустые строки
            Q(district=district) &
            ~Q(id__in=gazified_addresses)
        ).annotate(
            house_trimmed=Trim('house')
        ).exclude(
            house_trimmed__exact=''  # Исключаем строки, содержащие только пробелы
        ).distinct().values_list(
            'house', flat=True)            # Также получаем дома для записей, где district пустой, но city соответствует district
        city_houses = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(district__isnull=True) &
            Q(city=district) &
            street_condition &
            Q(house__isnull=False) &
            ~Q(house__exact='') &  # Исключаем пустые строки
            ~Q(id__in=gazified_addresses)
        ).annotate(
            house_trimmed=Trim('house')
        ).exclude(
            house_trimmed__exact=''  # Исключаем строки, содержащие только пробелы
        ).distinct().values_list(
            'house', flat=True)
        
        # Объединяем результаты
        all_houses = list(set(list(district_houses) + list(city_houses)))
        
        log_db_operation("read", "AddressV2", {
            "mo_id": mo_id, 
            "district": district,
            "street": street,
            "count": len(all_houses)
        })
        
        return create_response(
            data=HouseListResponse(houses=sorted(all_houses))
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка домов: {str(e)}")
