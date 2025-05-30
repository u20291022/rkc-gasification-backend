from fastapi import APIRouter
from app.api.v1.endpoints.addresses import (
    municipalities, streets, houses, apartments, rooms,
    structure, settlements, rural_houses, health
)

router = APIRouter()

# Включаем все роутеры для работы с адресными данными
router.include_router(municipalities.router, tags=["addresses"])
router.include_router(streets.router, tags=["addresses"])
router.include_router(houses.router, tags=["addresses"])
router.include_router(apartments.router, tags=["addresses"])
router.include_router(rooms.router, tags=["addresses"])
router.include_router(structure.router, tags=["addresses"])
router.include_router(settlements.router, tags=["addresses"])
router.include_router(rural_houses.router, tags=["addresses"])
router.include_router(health.router, tags=["addresses"])
