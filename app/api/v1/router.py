from fastapi import APIRouter
from app.api.v1.endpoints import gazification

router = APIRouter()
router.include_router(gazification.router, tags=["gazification"])
