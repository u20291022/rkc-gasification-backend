from fastapi import APIRouter
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import AddressCreateRequest
from app.models.models import AddressV2, GazificationData, TypeValue
from app.core.exceptions import DatabaseError
from tortoise.transactions import in_transaction

router = APIRouter()

@router.post("/add", response_model=BaseResponse)
async def add_address(request: AddressCreateRequest):
    """Добавление нового адреса"""
    try:        # Получаем запись типа значения с id=1 (предполагаем что это "Подключены к газу")
        try:
            type_value = await TypeValue.get(id=1)
        except Exception as e:
            raise DatabaseError(f"Не найден тип значения с id=1: {str(e)}")
        
        async with in_transaction() as conn:
            # Создаем новую запись в таблице адресов
            address = await AddressV2.create(
                id_mo=request.mo_id,
                district=request.district,
                city=request.district,
                street=request.street,
                house=request.house,
                flat=request.flat,
                is_mobile=True
            )
            
            # Создаем запись о газификации
            # id_type_address: 3 - подключены к газу, 4 - не подключены
            id_type_address = 3 if request.has_gas else 4

            await GazificationData.create(
                id_address=address.id,
                id_type_address=id_type_address,
                is_mobile=True
            )
            
            log_db_operation("create", "AddressV2 and GazificationData", {
                "mo_id": request.mo_id,
                "district": request.district,
                "street": request.street,
                "house": request.house,
                "has_gas": request.has_gas
            })
        
        return create_response(
            data=None,
            message="Адрес успешно добавлен"
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при добавлении адреса: {str(e)}")
