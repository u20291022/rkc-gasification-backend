from fastapi import APIRouter
from datetime import datetime, timezone
from app.core.utils import create_response, log_db_operation, record_activity
from app.schemas.base import BaseResponse
from app.schemas.gazification import AddressCreateRequest
from app.models.models import AddressV2, GazificationData, TypeValue
from app.core.exceptions import DatabaseError
from tortoise.transactions import in_transaction

router = APIRouter()


@router.post("/add", response_model=BaseResponse)
async def add_address(request: AddressCreateRequest):
    """Добавление нового адреса"""
    try:
        try:
            type_value = await TypeValue.get(id=1)
        except Exception as e:
            raise DatabaseError(f"Не найден тип значения с id=1: {str(e)}")
        async with in_transaction() as conn:
            district = request.district.strip() if request.district else None
            district = district if district else None
            street = request.street.strip() if request.street else None
            street = street if street else None
            house = request.house.strip() if request.house else None
            house = house.lower() if house else None
            flat = request.flat.strip() if request.flat else None
            flat = flat.lower() if flat else None
            address = await AddressV2.create(
                id_mo=request.mo_id,
                district=district,
                city=district,
                street=street,
                house=house,
                flat=flat,
                is_mobile=True,
                from_login=request.from_login,
            )
            id_type_address = 3 if request.has_gas else 4
            await GazificationData.create(
                id_address=address.id,
                id_type_address=id_type_address,
                is_mobile=True,
                from_login=request.from_login,
                date_create=datetime.now(timezone.utc),
            )
            log_db_operation(
                "create",
                "AddressV2 and GazificationData",
                {
                    "mo_id": request.mo_id,
                    "district": request.district,
                    "street": request.street,
                    "house": request.house,
                    "has_gas": request.has_gas,
                },
            )
            await record_activity(request.from_login or "unknown", request.session_id)
        return create_response(data=None, message="Адрес успешно добавлен")
    except Exception as e:
        raise DatabaseError(f"Ошибка при добавлении адреса: {str(e)}")
