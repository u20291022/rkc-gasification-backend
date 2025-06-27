from fastapi import APIRouter
from datetime import datetime, timezone
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
        address_query = AddressV2.filter(
            id_mo=request.mo_id, street=request.street, house=request.house
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
                id_type_address = 4
                if request.has_gas == "true":
                    id_type_address = 3
                elif request.has_gas == "not_exist":
                    id_type_address = 6
                elif request.has_gas == "not_at_home":
                    id_type_address = 7
                gazification_data = await GazificationData.filter(
                    id_address=address.id
                ).all()
                if gazification_data:
                    for gaz_data_curr in gazification_data:
                        gaz_data_curr.id_type_address = id_type_address
                        gaz_data_curr.from_login = request.from_login
                        gaz_data_curr.is_mobile = True
                        gaz_data_curr.date_create = datetime.now(timezone.utc)
                        await gaz_data_curr.save(
                            update_fields=[
                                "id_type_address",
                                "from_login",
                                "is_mobile",
                                "date_create",
                            ]
                        )
                else:
                    await GazificationData.create(
                        id_address=address.id,
                        id_type_address=id_type_address,
                        is_mobile=True,
                        from_login=request.from_login,
                        date_create=datetime.now(timezone.utc),
                    )
                log_db_operation(
                    "update",
                    "GazificationData",
                    {
                        "mo_id": request.mo_id,
                        "district": request.district,
                        "street": request.street,
                        "house": request.house,
                        "has_gas": request.has_gas,
                    },
                )
        await record_activity(request.from_login or "unknown", request.session_id)
        return create_response(data=None, message="Статус газификации успешно обновлен")
    except Exception as e:
        raise
