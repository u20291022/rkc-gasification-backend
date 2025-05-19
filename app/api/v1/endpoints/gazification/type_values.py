from fastapi import APIRouter
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import TypeValueModel, TypeValuesResponse
from app.models.models import TypeValue
from app.core.exceptions import DatabaseError

router = APIRouter()

@router.get("/type-values", response_model=BaseResponse[TypeValuesResponse])
async def get_type_values():
    """Получение списка типов значений"""
    try:
        type_values = await TypeValue.filter(for_mobile=True).all()

        log_db_operation("read", "TypeValue", {"count": len(type_values)})
        
        values_list = []
        for value in type_values:
            values_list.append(TypeValueModel(
                id=value.id,
                type_value=value.type_value or "",
                description=value.description
            ))
        
        return create_response(
            data=TypeValuesResponse(type_values=values_list)
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка типов значений: {str(e)}")
