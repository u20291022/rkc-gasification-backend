from fastapi import APIRouter
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import MOListResponse, MunicipalityModel
from app.models.models import AddressV2, Municipality
from app.core.exceptions import DatabaseError

router = APIRouter()

@router.get("/mo", response_model=BaseResponse[MOListResponse])
async def get_municipalities():
    """Получение списка муниципалитетов"""
    try:
        # Получаем только муниципалитеты с tip = 2
        municipalities = await Municipality.filter(tip=2).all()
        address_municipalities = await AddressV2.filter()
        
        # Получаем список id муниципалитетов из AddressV2
        address_mo_ids = set(addr.id_mo for addr in address_municipalities if addr.id_mo is not None)
        
        log_db_operation("read", "Municipality", {"count": len(municipalities)})
        
        mo_list = []
        for mo in municipalities:
            # Проверяем, что муниципалитет присутствует и в AddressV2
            if mo.id_parent in address_mo_ids:
                mo_list.append(MunicipalityModel(id=mo.id_parent, name=mo.name))
        
        return create_response(
            data=MOListResponse(mos=mo_list)
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка муниципалитетов: {str(e)}")
