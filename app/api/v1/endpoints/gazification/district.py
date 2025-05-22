from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import DistrictListResponse
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError
from tortoise.expressions import Q
from tortoise.functions import Coalesce

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
        # используя Coalesce для выбора district или city, если district отсутствует
        districts = await AddressV2.filter(
            Q(id_mo=mo_id) &
            Q(house__isnull=False) &
            ~Q(id__in=gazified_addresses)
        ).annotate(
            district_name=Coalesce('district', 'city')
        ).filter(
            district_name__isnull=False
        ).distinct().values_list(
            'district_name', flat=True)
        
        log_db_operation("read", "AddressV2", {"mo_id": mo_id, "count": len(districts)})
        
        return create_response(
            data=DistrictListResponse(districts=sorted(list(districts)))
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка районов: {str(e)}")
