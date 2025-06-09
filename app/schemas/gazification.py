from pydantic import BaseModel

# Схемы для работы с API газификации

class MunicipalityModel(BaseModel):
    """Модель муниципалитета для API"""
    id: int
    name: str


class MOListResponse(BaseModel):
    """Ответ со списком муниципалитетов"""
    mos: list[MunicipalityModel]


class DistrictListResponse(BaseModel):
    """Ответ со списком районов"""
    districts: list[str]


class StreetListResponse(BaseModel):
    """Ответ со списком улиц"""
    streets: list[str]


class HouseListResponse(BaseModel):
    """Ответ со списком домов"""
    houses: list[str]


class FlatListResponse(BaseModel):
    """Ответ со списком квартир"""
    flats: list[str]


class RelatedFieldModel(BaseModel):
    """Модель связанного поля"""
    field_id: int
    field_name: str


class ValueDependencyModel(BaseModel):
    """Модель зависимости значения на другое поле"""
    value: str
    related_field_id: int


class TypeValueModel(BaseModel):
    """Модель типа значения для API"""
    id: int
    order: int
    type_value: str
    description: str
    field_type: str | None = None  # Имя типа поля из таблицы FieldType
    related_fields: list[ValueDependencyModel] = []
    answers: list[str] = []
    answers_size: list[str] = []


class TypeValuesResponse(BaseModel):
    """Ответ со списком типов значений"""
    type_values: list[TypeValueModel]


class AddressCreateRequest(BaseModel):
    """Запрос на добавление адреса"""
    mo_id: int
    district: str
    street: str
    house: str
    flat: str | None = None
    has_gas: bool


class UpdateGasStatusRequest(BaseModel):
    """Запрос на обновление статуса газификации для существующего адреса"""
    mo_id: int
    district: str
    street: str
    house: str
    flat: str | None = None
    has_gas: bool


class AddressModel(BaseModel):
    """Модель адреса для запроса"""
    mo_id: int
    district: str
    street: str
    house: str
    flat: str | None = None


class FieldModel(BaseModel):
    """Модель поля для запроса"""
    id: int
    value: str  # true/false или текст


class GazificationUploadRequest(BaseModel):
    """Запрос на отправку записи"""
    address: AddressModel
    fields: list[FieldModel]
