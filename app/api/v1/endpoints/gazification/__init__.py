from fastapi import APIRouter
from app.api.v1.endpoints.gazification import (
    municipality,
    district,
    street,
    house,
    flat,
    add_address,
    upload,
    type_values,
    update_gas_status,
    export_excel,
    export_csv,
    export_activity,
    auth,
)

router = APIRouter()
router.include_router(municipality.router)
router.include_router(district.router)
router.include_router(street.router)
router.include_router(house.router)
router.include_router(flat.router)
router.include_router(add_address.router)
router.include_router(update_gas_status.router)
router.include_router(upload.router)
router.include_router(type_values.router)
router.include_router(export_excel.router)
router.include_router(export_csv.router)
router.include_router(export_activity.router)
router.include_router(auth.router, prefix="/auth", tags=["authentication"])
