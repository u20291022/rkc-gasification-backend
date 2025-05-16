from fastapi import APIRouter
from app.api.v1.endpoints import gazification

router = APIRouter()

# Используем газификацию напрямую, без префикса
router.include_router(gazification.router, tags=["gazification"])
