from fastapi import APIRouter
from app.api.v1.endpoints import gazification, addresses

router = APIRouter()

# Используем газификацию напрямую, без префикса
router.include_router(gazification.router, tags=["gazification"])

# Добавляем роутеры для работы с адресными подсказками
router.include_router(addresses.router, prefix="/addresses", tags=["addresses"])
