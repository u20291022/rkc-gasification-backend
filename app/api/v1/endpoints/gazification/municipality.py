from fastapi import APIRouter
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import MOListResponse, MunicipalityModel
from app.models.models import AddressV2, Municipality, GazificationData
from app.core.exceptions import DatabaseError
from tortoise.expressions import Q

router = APIRouter()

@router.get("/mo", response_model=BaseResponse[MOListResponse])
async def get_municipalities():
    """Получение списка муниципалитетов"""
    try:
        # Находим адреса, которые газифицированы (id_type_address = 3)
        gazified_addresses = await GazificationData.filter(
            id_type_address=3
        ).values_list('id_address', flat=True)
          # Оптимизированный запрос: получаем уникальные id_mo напрямую из БД
        valid_mo_ids = await AddressV2.filter(
            Q(house__isnull=False) &
            Q(id_mo__isnull=False) &
            ~Q(id__in=gazified_addresses)
        ).distinct().values_list(
            'id_mo', flat=True)
        
        # Получаем только муниципалитеты с tip = 1, которые есть в списке valid_mo_ids
        municipalities = await Municipality.filter(
            Q(tip=1) &
            Q(id__in=valid_mo_ids)
        ).all()
        
        log_db_operation("read", "Municipality", {"count": len(municipalities)})
        
        mo_list = [MunicipalityModel(id=mo.id, name=mo.name) for mo in municipalities]
        
        return create_response(
            data=MOListResponse(mos=mo_list)
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка муниципалитетов: {str(e)}")
