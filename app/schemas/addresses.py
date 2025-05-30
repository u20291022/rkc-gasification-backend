from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Схемы для работы с адресными данными (ГАР)

class Municipality(BaseModel):
    """Муниципальное образование"""
    id: int = Field(..., description="ID муниципального образования")
    name: str = Field(..., description="Название муниципального образования")
    type_name: str = Field(..., description="Краткое название типа")
    type_full_name: Optional[str] = Field(None, description="Полное название типа")
    related_ids: Optional[List[int]] = Field([], description="ID связанных объектов (например, городской округ для города)")

class Street(BaseModel):
    """Улица"""
    id: int = Field(..., description="ID улицы")
    name: str = Field(..., description="Название улицы")
    type_name: str = Field(..., description="Тип улицы (краткий)")
    municipality_id: int = Field(..., description="ID муниципального образования")
    municipality_name: str = Field(..., description="Название муниципального образования")

class House(BaseModel):
    """Дом"""
    id: int = Field(..., description="ID дома")
    house_num: Optional[str] = Field(None, description="Основной номер дома")
    add_num1: Optional[str] = Field(None, description="Дополнительный номер 1")
    add_num2: Optional[str] = Field(None, description="Дополнительный номер 2")
    house_type: Optional[str] = Field(None, description="Тип дома")
    add_type1: Optional[str] = Field(None, description="Дополнительный тип 1")
    add_type2: Optional[str] = Field(None, description="Дополнительный тип 2")
    full_number: str = Field(..., description="Полный номер дома")
    street_id: int = Field(..., description="ID улицы")
    street_name: str = Field(..., description="Название улицы")
    municipality_id: int = Field(..., description="ID муниципального образования")

class Apartment(BaseModel):
    """Квартира/помещение"""
    id: int = Field(..., description="ID квартиры")
    number: Optional[str] = Field(None, description="Номер квартиры")
    apart_type: Optional[str] = Field(None, description="Тип помещения")
    house_id: int = Field(..., description="ID дома")
    house_number: str = Field(..., description="Номер дома")
    street_name: str = Field(..., description="Название улицы")

class Room(BaseModel):
    """Комната"""
    id: int = Field(..., description="ID комнаты")
    number: Optional[str] = Field(None, description="Номер комнаты")
    room_type: Optional[str] = Field(None, description="Тип комнаты")
    apartment_id: int = Field(..., description="ID квартиры")
    apartment_number: str = Field(..., description="Номер квартиры")
    house_number: str = Field(..., description="Номер дома")

class Settlement(BaseModel):
    """Населенный пункт (деревня, село, СНТ и т.д.)"""
    id: int = Field(..., description="ID населенного пункта")
    object_id: int = Field(..., description="Object ID населенного пункта")
    name: str = Field(..., description="Название населенного пункта")
    type_name: str = Field(..., description="Тип населенного пункта (краткий)")
    type_full_name: Optional[str] = Field(None, description="Полное название типа")
    houses_count: int = Field(..., description="Количество домов в населенном пункте")

class RuralHouse(BaseModel):
    """Дом в сельской местности (без привязки к улице)"""
    id: int = Field(..., description="ID дома")
    object_id: int = Field(..., description="Object ID дома")
    house_num: Optional[str] = Field(None, description="Основной номер дома")
    add_num1: Optional[str] = Field(None, description="Дополнительный номер 1")
    add_num2: Optional[str] = Field(None, description="Дополнительный номер 2")
    full_address: str = Field(..., description="Полный номер дома")
    house_type_name: Optional[str] = Field(None, description="Тип дома")
    settlement_name: str = Field(..., description="Название населенного пункта")
    settlement_type: str = Field(..., description="Тип населенного пункта")

class AddressStructure(BaseModel):
    """Структура адресных данных для административной единицы"""
    id: int = Field(..., description="ID административной единицы")
    object_id: int = Field(..., description="Object ID административной единицы")
    name: str = Field(..., description="Название административной единицы")
    type_name: str = Field(..., description="Тип административной единицы")
    level: int = Field(..., description="Уровень в иерархии")
    level_name: Optional[str] = Field(None, description="Название уровня")
    streets_count: int = Field(..., description="Количество улиц")
    settlements_count: int = Field(..., description="Количество населенных пунктов")
    direct_houses_count: int = Field(..., description="Количество домов напрямую")
    has_streets: bool = Field(..., description="Есть ли улицы (городская структура)")
    has_settlements: bool = Field(..., description="Есть ли населенные пункты (сельская структура)")

class AddressSearchResponse(BaseModel):
    """Ответ поиска адресов"""
    total: int = Field(..., description="Общее количество результатов")
    items: List[Dict[str, Any]] = Field(..., description="Список результатов")

# Ответы для конкретных типов данных
class MunicipalityListResponse(BaseModel):
    """Ответ со списком муниципальных образований"""
    municipalities: List[Municipality]

class StreetListResponse(BaseModel):
    """Ответ со списком улиц"""
    streets: List[Street]

class HouseListResponse(BaseModel):
    """Ответ со списком домов"""
    houses: List[House]

class ApartmentListResponse(BaseModel):
    """Ответ со списком квартир"""
    apartments: List[Apartment]

class RoomListResponse(BaseModel):
    """Ответ со списком комнат"""
    rooms: List[Room]

class SettlementListResponse(BaseModel):
    """Ответ со списком населенных пунктов"""
    settlements: List[Settlement]

class RuralHouseListResponse(BaseModel):
    """Ответ со списком сельских домов"""
    rural_houses: List[RuralHouse]
