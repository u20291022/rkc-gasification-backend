from fastapi import APIRouter
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import TypeValueModel, TypeValuesResponse, RelatedFieldModel, ValueDependencyModel
from app.models.models import TypeValue, FieldType, FieldReference
from app.core.exceptions import DatabaseError
from typing import Dict, List, Optional
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/type-values", response_model=BaseResponse[TypeValuesResponse])
async def get_type_values():
    """Получение списка типов значений"""
    try:
        # 1. Получаем все типы значений для мобильного приложения
        type_values = await TypeValue.filter(for_mobile=True).order_by("order").all()
        log_db_operation("read", "TypeValue", {"count": len(type_values)})
        
        # 2. Получаем отображение ID типов полей на их имена
        field_type_mapping = await get_field_type_mapping()
          # 3. Получаем зависимости между полями
        field_references = await get_field_references()

        # 4. Преобразуем модели БД в модели API
        values_list = [
            convert_type_value_to_model(
                type_value,
                field_type_mapping.get(type_value.field_type_id) if type_value.field_type_id else None,
                field_references
            )
            for type_value in type_values
        ]
        
        # 5. Формируем и возвращаем ответ
        return create_response(
            data=TypeValuesResponse(type_values=values_list)
        )
    except Exception as e:
        logger.error(f"Ошибка при получении списка типов значений: {str(e)}", exc_info=True)
        raise DatabaseError(f"Ошибка при получении списка типов значений: {str(e)}")


async def get_field_type_mapping() -> Dict[int, str]:
    """Получаем отображение ID типов полей на их имена"""
    field_types = await FieldType.all()
    log_db_operation("read", "FieldType", {"count": len(field_types)})
    return {ft.field_type_id: ft.field_type_name for ft in field_types}


async def get_field_references() -> Dict[int, Dict[str, List[RelatedFieldModel]]]:
    """Получение зависимостей между полями"""
    references = await FieldReference.all()
    log_db_operation("read", "FieldReference", {"count": len(references)})
    logger.info(f"Загружено {len(references)} связей между полями")
    
    # Получаем отображение ID типов полей на их имена для внутреннего использования
    field_types = await FieldType.all()
    field_type_mapping = {ft.field_type_id: ft.field_type_name for ft in field_types}
    
    # Структура для хранения зависимостей полей:
    # {field_origin_id -> {field_origin_value -> [RelatedFieldModel]}}
    # Когда поле с field_origin_id получает значение field_origin_value,
    # должны показываться поля с id field_ref_id из списка
    result = {}
    
    for ref in references:
        # Получаем имя связанного поля или используем placeholder, если не найдено
        field_name = field_type_mapping.get(ref.field_ref_id, f"Unknown Field ({ref.field_ref_id})")
        
        # Нормализуем значение для согласованности
        normalized_value = str(ref.field_origin_value).lower().strip('"\'')
        
        # Инициализируем структуру, если она еще не существует
        if ref.field_origin_id not in result:
            result[ref.field_origin_id] = {}
            
        if normalized_value not in result[ref.field_origin_id]:
            result[ref.field_origin_id][normalized_value] = []
            
        # Добавляем связанное поле, которое должно отображаться
        result[ref.field_origin_id][normalized_value].append(
            RelatedFieldModel(
                field_id=ref.field_ref_id,
                field_name=field_name
            )
        )
    
    return result


def convert_type_value_to_model(
    type_value: TypeValue,
    field_type_name: Optional[str],
    field_references: Dict[int, Dict[str, List[RelatedFieldModel]]]
) -> TypeValueModel:
    """Преобразует модель БД в модель API"""
    related_fields = []
    
    # Всегда получаем связанные поля для этого типа значений, если field_type_id существует
    if type_value.id:
        # Если есть связанные поля в словаре field_references
        if type_value.id in field_references:
            for field_value, related_field_models in field_references[type_value.id].items():
                # Сохраняем булевы значения в правильном регистре
                original_value = field_value
                if field_value.lower() in ("true", "false"):
                    original_value = field_value.lower()
                    
                # Добавляем все связанные поля
                for related_field in related_field_models:
                    print(related_field)
                    related_fields.append(
                        ValueDependencyModel(
                            value=original_value,
                            related_field_id=related_field.field_id
                        )
                    )
        # Если нет связанных полей в словаре для этого типа поля, но field_type_id есть,
        # можно добавить какие-то стандартные связанные поля
        # (это место можно настроить под ваши конкретные требования)
    
    # Создаем и возвращаем модель для API
    return TypeValueModel(
        id=type_value.id,
        order=type_value.order,
        type_value=type_value.type_value or "",
        description=type_value.description,
        field_type=field_type_name,
        related_fields=related_fields or []  
    )
