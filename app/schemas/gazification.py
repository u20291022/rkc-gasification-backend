from pydantic import BaseModel
from typing import Optional, List

# Схемы для работы с API газификации

class MunicipalityModel(BaseModel):
    """Модель муниципалитета для API"""
    id: int
    name: str


class MOListResponse(BaseModel):
    """Ответ со списком муниципалитетов"""
    mos: List[MunicipalityModel]


class DistrictListResponse(BaseModel):
    """Ответ со списком районов"""
    districts: List[str]


class StreetListResponse(BaseModel):
    """Ответ со списком улиц"""
    streets: List[str]


class HouseListResponse(BaseModel):
    """Ответ со списком домов"""
    houses: List[str]


class FlatListResponse(BaseModel):
    """Ответ со списком квартир"""
    flats: List[str]


class TypeValueModel(BaseModel):
    """Модель типа значения для API"""
    id: int
    type_value: str


class TypeValuesResponse(BaseModel):
    """Ответ со списком типов значений"""
    type_values: List[TypeValueModel]


class AddressCreateRequest(BaseModel):
    """Запрос на добавление адреса"""
    mo_id: int
    district: str
    street: str
    house: str
    flat: Optional[str] = None
    has_gas: bool


class AddressModel(BaseModel):
    """Модель адреса для запроса"""
    mo_id: int
    district: str
    street: str
    house: str
    flat: Optional[str] = None


class FieldModel(BaseModel):
    """Модель поля для запроса"""
    id: int
    value: str  # true/false или текст


class GazificationUploadRequest(BaseModel):
    """Запрос на отправку записи"""
    address: AddressModel
    fields: List[FieldModel]
