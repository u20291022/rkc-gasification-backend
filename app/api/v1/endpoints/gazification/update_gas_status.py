from fastapi import APIRouter
from app.core.utils import create_response, log_db_operation, record_activity
from app.schemas.base import BaseResponse
from app.schemas.gazification import UpdateGasStatusRequest
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError, NotFoundError
from tortoise.transactions import in_transaction
from tortoise.expressions import Q

router = APIRouter()

@router.post("/update-gas-status", response_model=BaseResponse)
async def update_gas_status(request: UpdateGasStatusRequest):
    """Обновление статуса газификации для существующего адреса"""
    try:
        # Находим адрес по указанным параметрам, в соответствии с подходом в upload.py
        address_query = AddressV2.filter(
            id_mo=request.mo_id,
            street=request.street,
            house=request.house
        )
        
        if request.district:
            address_query = address_query.filter(
                Q(district=request.district) | Q(city=request.district)
            )
        else:
            address_query = address_query.filter(
                Q(district__isnull=True) & Q(city__isnull=True)
            )
            
        if request.flat:
            address_query = address_query.filter(flat=request.flat)
        else:
            address_query = address_query.filter(flat__isnull=True)
            
        addresses = await address_query.all()
        
        if not addresses:
            address_details = f"{request.mo_id}/{request.district or 'none'}/{request.street}/{request.house}/{request.flat or 'none'}"
            raise NotFoundError("Адрес не найден", address_details)
        for address in addresses:
            async with in_transaction() as conn:
                # id_type_address: 3 - подключены к газу, 4 - не подключены
                id_type_address = 4
                if request.has_gas == 'true':
                    id_type_address = 3
                elif request.has_gas == 'not_exist':
                    id_type_address = 6
                elif request.has_gas == 'not_at_home':
                    id_type_address = 7

                # Находим запись о газификации для данного адреса или создаем новую
                gazification_data = await GazificationData.filter(id_address=address.id).all()
                
                if gazification_data:
                    # Обновляем существующую запись
                    for gaz_data_curr in gazification_data:
                        gaz_data_curr.id_type_address = id_type_address
                        gaz_data_curr.from_login = request.from_login
                        gaz_data_curr.is_mobile = True
                        # Обновляем поля id_type_address и from_login, не трогая date_create
                        await gaz_data_curr.save(update_fields=['id_type_address', 'from_login', 'is_mobile'])
                else:
                    # Создаем новую запись о газификации
                    await GazificationData.create(
                        id_address=address.id,
                        id_type_address=id_type_address,
                        is_mobile=True,
                        from_login=request.from_login)
                
                log_db_operation("update", "GazificationData", {
                    "mo_id": request.mo_id,
                    "district": request.district,
                    "street": request.street,
                    "house": request.house,
                    "has_gas": request.has_gas
                })
        
        # Записываем активность пользователя
        await record_activity(request.from_login or "unknown", request.session_id)
        
        return create_response(
            data=None,
            message="Статус газификации успешно обновлен"
        )
    except Exception as e:
        raise
