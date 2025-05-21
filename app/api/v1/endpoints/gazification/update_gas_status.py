from fastapi import APIRouter
from pydantic import ValidationError
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import UpdateGasStatusRequest
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError, NotFoundError
from tortoise.transactions import in_transaction

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
            address_query = address_query.filter(district=request.district)
        else:
            address_query = address_query.filter(district__isnull=True)
            
        if request.flat:
            address_query = address_query.filter(flat=request.flat)
        else:
            address_query = address_query.filter(flat__isnull=True)
            
        address = await address_query.first()
        
        if not address:
            address_details = f"{request.mo_id}/{request.district or 'none'}/{request.street}/{request.house}/{request.flat or 'none'}"
            raise NotFoundError("Адрес не найден", address_details)
            
        async with in_transaction() as conn:
            # id_type_address: 3 - подключены к газу, 4 - не подключены
            id_type_address = 3 if request.has_gas else 4
            
            # Находим запись о газификации для данного адреса или создаем новую
            gazification_data = await GazificationData.filter(id_address=address.id).all()
            
            if gazification_data:
                # Обновляем существующую запись
                for gaz_data_curr in gazification_data:
                    gaz_data_curr.id_type_address = id_type_address
                    await gaz_data_curr.save()
            else:
                # Создаем новую запись о газификации
                await GazificationData.create(
                    id_address=address.id,
                    id_type_address=id_type_address,
                )
            
            log_db_operation("update", "GazificationData", {
                "mo_id": request.mo_id,
                "district": request.district,
                "street": request.street,
                "house": request.house,
                "has_gas": request.has_gas
            })
        
        return create_response(
            data=None,
            message="Статус газификации успешно обновлен"
        )
    except Exception as e:
        raise
