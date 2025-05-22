from fastapi import APIRouter
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import TypeValueModel, TypeValuesResponse, RelatedFieldModel, ValueDependencyModel
from app.models.models import FieldAnswer, TypeValue, FieldType, FieldReference
from app.core.exceptions import DatabaseError
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/type-values", response_model=BaseResponse[TypeValuesResponse])
async def get_type_values():
    """Получение списка типов значений"""
    try:
        type_values = await TypeValue.filter(for_mobile=True).order_by("order").prefetch_related()
        log_db_operation("read", "TypeValue", {"count": len(type_values)})
        
        field_types = await FieldType.all()
        field_type_mapping = {ft.field_type_id: ft.field_type_name for ft in field_types}
        log_db_operation("read", "FieldType", {"count": len(field_types)})
        
        references = await FieldReference.all()
        log_db_operation("read", "FieldReference", {"count": len(references)})
        
        field_references = {}
        for ref in references:
            normalized_value = str(ref.field_origin_value).lower().strip('"\'')
            
            if ref.field_origin_id not in field_references:
                field_references[ref.field_origin_id] = {}
                
            if normalized_value not in field_references[ref.field_origin_id]:
                field_references[ref.field_origin_id][normalized_value] = []
                
            field_references[ref.field_origin_id][normalized_value].append(
                RelatedFieldModel(
                    field_id=ref.field_ref_id,
                    field_name=field_type_mapping.get(ref.field_ref_id, f"Unknown Field ({ref.field_ref_id})")
                )
            )

        values_list = []
        for type_value in type_values:
            related_fields = []
            
            if type_value.id and type_value.id in field_references:
                for field_value, related_field_models in field_references[type_value.id].items():
                    original_value = field_value
                    if field_value.lower() in ("true", "false"):
                        original_value = field_value.lower()
                        
                    for related_field in related_field_models:
                        related_fields.append(
                            ValueDependencyModel(
                                value=original_value,
                                related_field_id=related_field.field_id
                            )
                        )
            
            answers = await FieldAnswer.filter(type_value_id=type_value.id).all()
            if not answers:
                answers = [answer.field_answer_value for answer in answers]
            else:
                answers = []

            values_list.append(
                TypeValueModel(
                    id=type_value.id,
                    order=type_value.order,
                    type_value=type_value.type_value or "",
                    description=type_value.description,
                    field_type=field_type_mapping.get(type_value.field_type_id) if type_value.field_type_id else None,
                    related_fields=related_fields,
                    answers=answers
                )
            )
        
        return create_response(
            data=TypeValuesResponse(type_values=values_list)
        )
    except Exception as e:
        logger.error(f"Ошибка при получении списка типов значений: {str(e)}", exc_info=True)
        raise DatabaseError(f"Ошибка при получении списка типов значений: {str(e)}")
