from fastapi import APIRouter
from datetime import datetime, timezone
from app.core.utils import create_response, log_db_operation, record_activity
from app.schemas.base import BaseResponse
from app.schemas.gazification import GazificationUploadRequest
from app.models.models import AddressV2, GazificationData, TypeValue
from app.core.exceptions import DatabaseError, ValidationError
from tortoise.transactions import in_transaction
from tortoise.expressions import Q

router = APIRouter()


@router.post("/upload", response_model=BaseResponse)
async def upload_gazification_data(request: GazificationUploadRequest):
    """Отправка записи о газификации"""
    try:
        for field in request.fields:
            try:
                await TypeValue.get(id=field.id)
            except Exception as e:
                raise ValidationError(f"Тип значения с id={field.id} не найден")
        address_query = AddressV2.filter(
            id_mo=request.address.mo_id,
            street=request.address.street,
            house=request.address.house,
            deleted=False,
        )
        if request.address.district:
            # Район может быть в поле district или city
            address_query = address_query.filter(
                Q(district=request.address.district) | Q(city=request.address.district)
            )
        else:
            # Если район не передан, ищем где оба поля NULL
            address_query = address_query.filter(district__isnull=True, city__isnull=True)
        if request.address.flat:
            address_query = address_query.filter(flat=request.address.flat)
        else:
            address_query = address_query.filter(flat__isnull=True)
        address = await address_query.first()
        async with in_transaction() as conn:
            if not address:
                address = await AddressV2.create(
                    id_mo=request.address.mo_id,
                    district=request.address.district,
                    city=request.address.district,
                    street=request.address.street,
                    house=request.address.house,
                    flat=request.address.flat,
                    is_mobile=True,
                    from_login=request.from_login,
                )
                log_db_operation(
                    "create",
                    "AddressV2",
                    {
                        "address_id": address.id,
                        "mo_id": request.address.mo_id,
                        "district": request.address.district,
                        "street": request.address.street,
                        "house": request.address.house,
                        "flat": request.address.flat,
                    },
                )
            # Помечаем все существующие записи газификации по адресу как удаленные
            await GazificationData.filter(
                id_address=address.id,
                deleted=False
            ).update(deleted=True)
            
            for field in request.fields:
                type_value = await TypeValue.get(id=field.id)
                await GazificationData.create(
                    id_address=address.id,
                    id_type_address=4,
                    id_type_value=type_value.id,
                    value=field.value,
                    is_mobile=True,
                    from_login=request.from_login,
                    date_create=datetime.now(timezone.utc),
                )
            log_db_operation(
                "create",
                "GazificationData",
                {"address_id": address.id, "fields_count": len(request.fields)},
            )
            await record_activity(request.from_login or "unknown", request.session_id)
        return create_response(data=None, message="Данные успешно сохранены")
    except Exception as e:
        raise DatabaseError(f"Ошибка при сохранении данных: {str(e)}")
