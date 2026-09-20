"""Published restaurant map queries / 已發布店家的公開地圖查詢。"""

from __future__ import annotations

import uuid

from geoalchemy2 import Geography
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models import Restaurant
from api.schemas import MapCuisineResponse, MapRestaurantResponse, PriceRange


async def query_public_restaurants(
    session: AsyncSession,
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    cuisine_ids: list[uuid.UUID] | None,
    price_ranges: list[PriceRange] | None,
    result_limit: int,
) -> tuple[list[MapRestaurantResponse], bool]:
    """Return published restaurants inside one bounded map viewport.

    回傳地圖可視範圍內的已發布店家，並以多取一筆判斷是否需要放大地圖。
    """
    viewport = func.ST_MakeEnvelope(west, south, east, north, 4326).cast(
        Geography(geometry_type="POLYGON", srid=4326)
    )
    statement: Select[tuple[Restaurant]] = (
        select(Restaurant)
        .options(selectinload(Restaurant.primary_cuisine))
        .where(
            Restaurant.status == "published",
            Restaurant.location.is_not(None),
            Restaurant.primary_cuisine_id.is_not(None),
            Restaurant.price_range.is_not(None),
            func.ST_Intersects(Restaurant.location, viewport),
        )
        .order_by(Restaurant.updated_at.desc(), Restaurant.id)
        .limit(result_limit + 1)
    )
    if cuisine_ids:
        statement = statement.where(Restaurant.primary_cuisine_id.in_(cuisine_ids))
    if price_ranges:
        statement = statement.where(Restaurant.price_range.in_(price_ranges))

    restaurants = list((await session.execute(statement)).scalars())
    if len(restaurants) > result_limit:
        return [], True

    results: list[MapRestaurantResponse] = []
    for restaurant in restaurants:
        cuisine = restaurant.primary_cuisine
        if (
            cuisine is None
            or restaurant.latitude is None
            or restaurant.longitude is None
            or restaurant.price_range is None
        ):
            continue
        results.append(
            MapRestaurantResponse(
                id=restaurant.id,
                name=restaurant.name,
                latitude=restaurant.latitude,
                longitude=restaurant.longitude,
                primary_cuisine=MapCuisineResponse(
                    id=cuisine.id,
                    display_name=cuisine.display_name,
                    color=cuisine.color,
                    icon_key=cuisine.icon_key,
                ),
                price_range=restaurant.price_range,  # type: ignore[arg-type]
                menu_url=restaurant.menu_url,
            )
        )
    return results, False
