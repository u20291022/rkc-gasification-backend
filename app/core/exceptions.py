from fastapi import HTTPException
from app.core.logging import get_logger

logger = get_logger("exceptions")

class ValidationError(HTTPException):
    def __init__(self, detail):
        logger.warning(f"Validation error: {detail}")
        super().__init__(status_code=400, detail=detail)

class NotFoundError(HTTPException):
    def __init__(self, resource_type, resource_id):
        detail = f"{resource_type} c id {resource_id} не найден"
        logger.warning(f"Resource not found: {detail}")
        super().__init__(status_code=404, detail=detail)

class DatabaseError(HTTPException):
    def __init__(self, detail="Неуспешная операция в базе данных"):
        logger.error(f"Database error: {detail}")
        super().__init__(status_code=500, detail=detail)

