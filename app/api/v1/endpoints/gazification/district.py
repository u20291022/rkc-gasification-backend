from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import DistrictListResponse
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError
from tortoise.expressions import Q, Case, When, F
from tortoise.functions import Coalesce

router = APIRouter()


@router.get("/mo/{mo_id}/district", response_model=BaseResponse[DistrictListResponse])
async def get_districts(mo_id: int = Path()):
    """Получение списка районов по ID муниципалитета"""
    try:
        gazified_addresses = await GazificationData.filter(
            (Q(id_type_address=3) | Q(id_type_address=6) | Q(id_type_address=8)) & Q(deleted=False)
        ).values_list("id_address", flat=True)
        district_addresses = (
            await AddressV2.filter(
                Q(id_mo=mo_id)
                & Q(house__isnull=False)
                & Q(district__isnull=False)
                & ~Q(district="")
                & ~Q(id__in=gazified_addresses)
                & Q(deleted=False)
            )
            .distinct()
            .values_list("district", flat=True)
        )
        city_addresses = (
            await AddressV2.filter(
                Q(id_mo=mo_id)
                & Q(house__isnull=False)
                & Q(district__isnull=True)
                & Q(city__isnull=False)
                & ~Q(city="")
                & ~Q(id__in=gazified_addresses)
                & Q(deleted=False)
            )
            .distinct()
            .values_list("city", flat=True)
        )
        all_districts = list(district_addresses) + list(city_addresses)
        filtered_districts = []
        for district in all_districts:
            if district and district.strip():
                filtered_districts.append(district.strip())
        districts = list(set(filtered_districts))
        log_db_operation("read", "AddressV2", {"mo_id": mo_id, "count": len(districts)})
        return create_response(
            data=DistrictListResponse(districts=sorted(list(districts)))
        )
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка районов: {str(e)}")
