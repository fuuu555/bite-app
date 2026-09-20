"""Published restaurant map queries / 已發布店家的公開地圖查詢。"""

from __future__ import annotations

import uuid

from geoalchemy2 import Geography
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.domain.models import Cuisine, Restaurant
from api.domain.schemas import MapCuisineResponse, MapRestaurantResponse, PriceRange


async def query_public_restaurants(
    session: AsyncSession,
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    cuisine_ids: list[uuid.UUID] | None,
    price_ranges: list[PriceRange] | None,
    city: str | None,
    district: str | None,
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
    if city:
        statement = statement.where(_normalized_address().contains(_normalize_area_term(city)))
    if district:
        statement = statement.where(_normalized_address().contains(_normalize_area_term(district)))

    restaurants = list((await session.execute(statement)).scalars())
    if len(restaurants) > result_limit:
        return [], True

    return [
        _restaurant_response(restaurant)
        for restaurant in restaurants
        if _is_map_ready(restaurant)
    ], False


def _is_map_ready(restaurant: Restaurant) -> bool:
    return (
        restaurant.primary_cuisine is not None
        and restaurant.latitude is not None
        and restaurant.longitude is not None
        and restaurant.price_range is not None
    )


def _normalize_area_term(value: str) -> str:
    """Match common 台／臺 spelling variants in stored addresses."""
    return value.strip().lower().replace("台", "臺")


def _normalized_address():
    """Normalize common 台／臺 spelling variants before area filtering."""
    return func.replace(func.lower(Restaurant.address), "台", "臺")


def _restaurant_response(restaurant: Restaurant) -> MapRestaurantResponse:
    """Convert a validated restaurant to the public map contract.

    將已通過地圖必要欄位驗證的店家轉成公開地圖資料契約。
    """
    cuisine = restaurant.primary_cuisine
    if (
        not _is_map_ready(restaurant)
        or cuisine is None
        or restaurant.latitude is None
        or restaurant.longitude is None
        or restaurant.price_range is None
    ):
        raise ValueError("restaurant is missing public map fields")
    return MapRestaurantResponse(
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


async def query_public_restaurant_search(
    session: AsyncSession,
    *,
    query: str,
    result_limit: int,
) -> list[MapRestaurantResponse]:
    """Search published restaurants by name or address / 搜尋已發布店家名稱或地址。"""
    term = query.strip().lower()
    statement: Select[tuple[Restaurant]] = (
        select(Restaurant)
        .options(selectinload(Restaurant.primary_cuisine))
        .where(
            Restaurant.status == "published",
            Restaurant.location.is_not(None),
            Restaurant.primary_cuisine_id.is_not(None),
            Restaurant.price_range.is_not(None),
            or_(
                func.lower(Restaurant.name).contains(term),
                func.lower(Restaurant.address).contains(term),
            ),
        )
        .order_by(Restaurant.updated_at.desc(), Restaurant.id)
        .limit(result_limit)
    )
    restaurants = (await session.execute(statement)).scalars()
    return [_restaurant_response(item) for item in restaurants if _is_map_ready(item)]


async def list_active_cuisines(session: AsyncSession) -> list[MapCuisineResponse]:
    """List active cuisines for public filters / 提供公開篩選使用的啟用料理分類。"""
    statement: Select[tuple[Cuisine]] = (
        select(Cuisine).where(Cuisine.is_active.is_(True)).order_by(Cuisine.display_name)
    )
    cuisines = (await session.execute(statement)).scalars()
    return [
        MapCuisineResponse(
            id=cuisine.id,
            display_name=cuisine.display_name,
            color=cuisine.color,
            icon_key=cuisine.icon_key,
        )
        for cuisine in cuisines
    ]
