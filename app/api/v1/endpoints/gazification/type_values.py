from fastapi import APIRouter
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import TypeValueModel, TypeValuesResponse, RelatedFieldModel, ValueDependencyModel
from app.models.models import TypeValue, FieldType, FieldReference
from app.core.exceptions import DatabaseError
from collections import defaultdict

router = APIRouter()

@router.get("/type-values", response_model=BaseResponse[TypeValuesResponse])
async def get_type_values():
    """Получение списка типов значений"""
    try:
        type_values = await TypeValue.filter(for_mobile=True).all()
        log_db_operation("read", "TypeValue", {"count": len(type_values)})
        
        # Заранее получаем все типы полей
        all_field_types = {ft.field_type_id: ft for ft in await FieldType.all()}
        
        # Получаем все связи между полями и группируем их по полю-источнику
        field_refs_by_origin_id = defaultdict(list)
        for ref in await FieldReference.all():
            field_refs_by_origin_id[ref.field_origin_id].append(ref)
        
        values_list = []
        for value in type_values:
            related_fields = []
            
            # Получаем имя типа поля если есть field_type_id
            field_type_name = None
            if value.field_type_id and value.field_type_id in all_field_types:
                field_type_name = all_field_types[value.field_type_id].field_type_name
            
            # Если есть связанный field_type_id, добавляем все его связи
            if value.field_type_id and value.field_type_id in field_refs_by_origin_id:
                for ref in field_refs_by_origin_id[value.field_type_id]:
                    # Получаем связанное поле
                    related_field_type = all_field_types.get(ref.field_ref_id)
                    if related_field_type:
                        # Добавляем зависимость значения на другое поле
                        related_fields.append(
                            ValueDependencyModel(
                                value=ref.field_origin_value,
                                related_field=RelatedFieldModel(
                                    field_id=related_field_type.field_type_id,
                                    field_name=related_field_type.field_type_name
                                )
                            )
                        )
            
            # Создаем модель типа значения с информацией о связанных полях
            values_list.append(TypeValueModel(
                id=value.id,
                type_value=value.type_value or "",
                description=value.description,
                field_type=field_type_name,
                related_fields=related_fields
            ))
        
        return create_response(
            data=TypeValuesResponse(type_values=values_list)
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка типов значений: {str(e)}")
