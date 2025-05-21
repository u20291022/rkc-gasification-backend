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
        
        # Получаем адреса, которые не газифицированы и имеют дом
        valid_addresses = await AddressV2.filter(
            Q(house__isnull=False) &
            ~Q(id__in=gazified_addresses)
        )
        
        # Получаем список id муниципалитетов из отфильтрованных адресов
        valid_mo_ids = set(addr.id_mo for addr in valid_addresses if addr.id_mo is not None)
        
        # Получаем только муниципалитеты с tip = 1, которые есть в списке valid_mo_ids
        municipalities = await Municipality.filter(tip=1).all()
        
        log_db_operation("read", "Municipality", {"count": len(municipalities)})
        
        mo_list = []
        for mo in municipalities:
            # Проверяем, что муниципалитет присутствует в списке валидных муниципалитетов
            if mo.id in valid_mo_ids:
                mo_list.append(MunicipalityModel(id=mo.id, name=mo.name))
        
        return create_response(
            data=MOListResponse(mos=mo_list)
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка муниципалитетов: {str(e)}")
