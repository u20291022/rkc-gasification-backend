from fastapi import APIRouter
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import TypeValueModel, TypeValuesResponse, RelatedFieldModel, ValueDependencyModel
from app.models.models import TypeValue, FieldType, FieldReference
from app.core.exceptions import DatabaseError
from collections import defaultdict
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/type-values", response_model=BaseResponse[TypeValuesResponse])
async def get_type_values():
    """Получение списка типов значений"""
    try:
        # Получаем все типы значений для мобильного приложения
        type_values = await TypeValue.filter(for_mobile=True).order_by("order").all()
        log_db_operation("read", "TypeValue", {"count": len(type_values)})
        
        # Получаем все типы полей для быстрого доступа
        all_field_types = {ft.field_type_id: ft for ft in await FieldType.all()}
        
        # Получаем все связи между полями
        all_references = await FieldReference.all()
        
        logger.info(f"Загружено {len(all_references)} связей между полями")
        
        # Создаем словарь связей поле -> (значение -> связанное поле)
        field_value_references = defaultdict(dict)
        for ref in all_references:
            logger.debug(f"Обрабатываю связь: origin_id={ref.field_origin_id}, value='{ref.field_origin_value}', ref_id={ref.field_ref_id}")
            
            # Проверяем существование целевого поля
            if ref.field_ref_id in all_field_types:
                # Нормализуем значение (приводим к нижнему регистру)
                normalized_value = str(ref.field_origin_value).lower().strip('"\'')
                
                if normalized_value not in field_value_references[ref.field_origin_id]:
                    field_value_references[ref.field_origin_id][normalized_value] = []
                
                field_value_references[ref.field_origin_id][normalized_value].append(
                    RelatedFieldModel(
                        field_id=ref.field_ref_id,
                        field_name=all_field_types[ref.field_ref_id].field_type_name
                    )
                )
            else:
                logger.warning(f"Целевое поле {ref.field_ref_id} не найдено в списке типов полей")
        
        # Формируем результат
        values_list = []
        for value in type_values:
            # Получаем имя типа поля если есть field_type_id
            field_type_name = None
            if value.field_type_id and value.field_type_id in all_field_types:
                field_type_name = all_field_types[value.field_type_id].field_type_name
            
            # Собираем связанные поля
            related_fields = []
            if value.field_type_id in field_value_references:
                for field_value, related_field_models in field_value_references[value.field_type_id].items():
                    # Для каждого связанного поля создаем модель зависимости
                    for related_field in related_field_models:
                        # Используем исходное значение для возврата клиенту
                        # (не нормализованное, как в базе данных)
                        original_value = field_value
                        if field_value.lower() == "false":
                            original_value = "false"
                        elif field_value.lower() == "true":
                            original_value = "true"
                        
                        related_fields.append(
                            ValueDependencyModel(
                                value=original_value,
                                related_field=related_field
                            )
                        )
            
            # Создаем модель типа значения для API
            values_list.append(TypeValueModel(
                id=value.id,
                order=value.order,
                type_value=value.type_value or "",
                description=value.description,
                field_type=field_type_name,
                related_fields=related_fields
            ))
        
        return create_response(
            data=TypeValuesResponse(type_values=values_list)
        )
    except Exception as e:
        logger.error(f"Ошибка при получении списка типов значений: {str(e)}", exc_info=True)
        raise DatabaseError(f"Ошибка при получении списка типов значений: {str(e)}")
