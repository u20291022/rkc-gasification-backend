from fastapi import APIRouter
from app.api.v1.endpoints.gazification import municipality, district, street, house, flat, add_address, upload, type_values, update_gas_status

router = APIRouter()

# Организуем роуты в соответствии с документацией (Опросник Газификация.md)
router.include_router(municipality.router)
router.include_router(district.router)
router.include_router(street.router)
router.include_router(house.router)
router.include_router(flat.router)
router.include_router(add_address.router)
router.include_router(update_gas_status.router)
router.include_router(upload.router)
router.include_router(type_values.router)
