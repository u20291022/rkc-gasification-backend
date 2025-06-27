from fastapi import APIRouter, Path
from app.core.utils import create_response, log_db_operation
from app.schemas.base import BaseResponse
from app.schemas.gazification import HouseListResponse
from app.models.models import AddressV2, GazificationData
from app.core.exceptions import DatabaseError
from tortoise.expressions import Q

router = APIRouter()


@router.get(
    "/mo/{mo_id}/district/{district}/street/{street}/house",
    response_model=BaseResponse[HouseListResponse],
)
async def get_houses(mo_id: int = Path(), district: str = Path(), street: str = Path()):
    """Получение списка домов по ID муниципалитета, району и улице"""
    try:
        gazified_addresses = await GazificationData.filter(
            Q(id_type_address=3) | Q(id_type_address=6)
        ).values_list("id_address", flat=True)
        street_condition = Q(street=street)
        if street == "" or street == "Нет улиц":
            street_condition = Q(street="") | Q(street__isnull=True)
        district_houses = (
            await AddressV2.filter(
                Q(id_mo=mo_id)
                & street_condition
                & Q(house__isnull=False)
                & ~Q(house="")
                & Q(district__isnull=False)
                & ~Q(district="")
                & ~Q(id__in=gazified_addresses)
            )
            .distinct()
            .values_list("house", "district", flat=False)
        )
        city_houses = (
            await AddressV2.filter(
                Q(id_mo=mo_id)
                & Q(district__isnull=True)
                & Q(city__isnull=False)
                & ~Q(city="")
                & street_condition
                & Q(house__isnull=False)
                & ~Q(house="")
                & ~Q(id__in=gazified_addresses)
            )
            .distinct()
            .values_list("house", "city", flat=False)
        )
        filtered_houses = []
        for house, district_name in district_houses:
            if (
                house
                and house.strip()
                and district_name
                and district_name.strip() == district
            ):
                filtered_houses.append(house.strip())
        for house, city_name in city_houses:
            if house and house.strip() and city_name and city_name.strip() == district:
                filtered_houses.append(house.strip())
        all_houses = list(set(filtered_houses))
        log_db_operation(
            "read",
            "AddressV2",
            {
                "mo_id": mo_id,
                "district": district,
                "street": street,
                "count": len(all_houses),
            },
        )
        return create_response(data=HouseListResponse(houses=sorted(all_houses)))
    except Exception as e:
        raise DatabaseError(f"Ошибка при получении списка домов: {str(e)}")
