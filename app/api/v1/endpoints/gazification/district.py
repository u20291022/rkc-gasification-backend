from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import DistrictListResponse
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError
from tortoise.expressions import Q, Case, When, F
from tortoise.functions import Coalesce, Trim

router = APIRouter()

@router.get("/mo/{mo_id}/district", response_model=BaseResponse[DistrictListResponse])
async def get_districts(mo_id: int = Path()):
    """Получение списка районов по ID муниципалитета"""
    try:
        # Находим адреса, которые газифицированы (id_type_address = 3)
        gazified_addresses = await GazificationData.filter(
            id_type_address=3
        ).values_list('id_address', flat=True)
        # Оптимизированный запрос: получаем уникальные районы напрямую из БД
        # используя Case/When для обработки логики выбора district или city
        districts = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(house__isnull=False) &
            ~Q(id__in=gazified_addresses)
            ).annotate(
            district=Case(
                When(Q(district__isnull=False) & ~Q(district=''), then=F('district')),
                default=F('city')
            )
        ).filter(
            district__isnull=False
        ).exclude(
            district__exact=''  # Исключаем пустые строки
        ).annotate(
            district_trimmed=Trim('district')
        ).exclude(
            district_trimmed__exact=''  # Исключаем строки, содержащие только пробелы
        ).distinct().values_list(
            'district', flat=True)
        log_db_operation("read", "AddressV2", {"mo_id": mo_id, "count": len(districts)})
        
        return create_response(
            data=DistrictListResponse(districts=sorted(list(districts)))
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка районов: {str(e)}")
