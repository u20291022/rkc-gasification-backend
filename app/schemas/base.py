from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")


class BaseResponse(GenericModel, Generic[T]):
    ok: bool
    message: str
    data: Optional[T] = None
