"""Restaurant exploration queries / 餐廳探索查詢。"""

from __future__ import annotations

import uuid
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.domain.models import Restaurant
from api.domain.schemas import (
    ExploreAppSignalsResponse,
    ExploreDistanceKm,
    ExploreGoogleSignalsResponse,
    ExploreMenuDocumentResponse,
    ExploreMenuResponse,
    ExplorePhotoResponse,
    ExploreRestaurantDetailResponse,
    ExploreRestaurantsResponse,
    ExploreRestaurantSummaryResponse,
    MapCuisineResponse,
    PriceRange,
)
from api.services.ranking import RestaurantRanking, stable_restaurant_ranking
from api.services.reviews import get_restaurant_app_stats


async def query_explore_restaurants(
    session: AsyncSession,
    *,
    query: str | None,
    cuisine_ids: list[uuid.UUID] | None,
    price_ranges: list[PriceRange] | None,
    latitude: float | None,
    longitude: float | None,
    distance_km: ExploreDistanceKm | None,
    result_limit: int,
    ranking: RestaurantRanking = stable_restaurant_ranking,
) -> ExploreRestaurantsResponse:
    """Search existing published restaurants with an explicit stable order.

    搜尋既有已發布店家；綜合分數尚未確認，因此只提供明確穩定排序。
    """
    statement: Select[Any] = (
        select(Restaurant)
        .options(
            selectinload(Restaurant.primary_cuisine),
            selectinload(Restaurant.menus),
            selectinload(Restaurant.photos),
        )
        .where(
            Restaurant.status == "published",
            Restaurant.primary_cuisine_id.is_not(None),
            Restaurant.price_range.is_not(None),
        )
        .order_by(func.lower(Restaurant.name), Restaurant.id)
    )
    origin = _origin_point(latitude, longitude)
    if origin is not None:
        statement = statement.add_columns(func.ST_Distance(Restaurant.location, origin))
        statement = statement.where(Restaurant.location.is_not(None))
        if distance_km is not None:
            statement = statement.where(
                func.ST_DWithin(Restaurant.location, origin, distance_km * 1000),
            )
    if query:
        statement = statement.where(func.lower(Restaurant.name).contains(query.casefold()))
    if cuisine_ids:
        statement = statement.where(Restaurant.primary_cuisine_id.in_(cuisine_ids))
    if price_ranges:
        statement = statement.where(Restaurant.price_range.in_(price_ranges))
    statement = statement.limit(result_limit)

    rows = list((await session.execute(statement)).all())
    if origin is None:
        restaurants = [row[0] for row in rows]
        distances: dict[uuid.UUID, float | None] = {}
    else:
        restaurants = [row[0] for row in rows]
        distances = {row[0].id: float(row[1]) for row in rows}
    ranked = ranking.rank(restaurants)
    app_stats = await get_restaurant_app_stats(session, [item.id for item in restaurants])
    responses = [
        _summary_response(
            item,
            distance_meters=distances.get(item.id),
            app_signals=app_stats.get(item.id),
        )
        for item in ranked
        if _is_explore_ready(item)
    ]
    return ExploreRestaurantsResponse(
        query=query,
        sort=ranking.key,
        top_restaurants=responses[:3],
        restaurants=responses,
    )


async def get_explore_restaurant(
    session: AsyncSession,
    restaurant_id: uuid.UUID,
    *,
    latitude: float | None,
    longitude: float | None,
) -> ExploreRestaurantDetailResponse | None:
    """Return one published restaurant for the shared detail route / 取得公開餐廳詳情。"""
    origin = _origin_point(latitude, longitude)
    statement: Select[Any] = (
        select(Restaurant)
        .options(
            selectinload(Restaurant.primary_cuisine),
            selectinload(Restaurant.menus),
            selectinload(Restaurant.photos),
        )
        .where(Restaurant.id == restaurant_id, Restaurant.status == "published")
    )
    if origin is not None:
        statement = statement.add_columns(func.ST_Distance(Restaurant.location, origin))
        statement = statement.where(Restaurant.location.is_not(None))
    row = (await session.execute(statement)).first()
    restaurant = row[0] if row else None
    if restaurant is None or not _is_explore_ready(restaurant):
        return None

    summary = _summary_response(
        restaurant,
        distance_meters=(
            float(row[1]) if origin is not None and row and row[1] is not None else None
        ),
        app_signals=(await get_restaurant_app_stats(session, [restaurant.id])).get(restaurant.id),
    )
    return ExploreRestaurantDetailResponse(
        **summary.model_dump(),
        latitude=restaurant.latitude,
        longitude=restaurant.longitude,
        menu=ExploreMenuResponse(url=restaurant.menu_url),
        menus=[
            ExploreMenuDocumentResponse(
                id=menu.id,
                title=menu.title,
                url=menu.url,
                last_updated_at=menu.last_updated_at,
            )
            for menu in restaurant.menus
        ],
        photos=[
            ExplorePhotoResponse(id=photo.id, url=photo.url, alt_text=photo.alt_text)
            for photo in restaurant.photos
        ],
    )


def _is_explore_ready(restaurant: Restaurant) -> bool:
    return restaurant.primary_cuisine is not None and restaurant.price_range is not None


def _summary_response(
    restaurant: Restaurant,
    *,
    distance_meters: float | None = None,
    app_signals: ExploreAppSignalsResponse | None = None,
) -> ExploreRestaurantSummaryResponse:
    cuisine = restaurant.primary_cuisine
    if cuisine is None or restaurant.price_range is None:
        raise ValueError("restaurant is missing exploration fields")
    return ExploreRestaurantSummaryResponse(
        id=restaurant.id,
        name=restaurant.name,
        address=restaurant.address,
        primary_cuisine=MapCuisineResponse(
            id=cuisine.id,
            display_name=cuisine.display_name,
            color=cuisine.color,
            icon_key=cuisine.icon_key,
        ),
        price_range=restaurant.price_range,  # type: ignore[arg-type]
        menu_url=restaurant.menu_url,
        photo_url=restaurant.photos[0].url if restaurant.photos else None,
        distance_meters=distance_meters,
        app=app_signals or ExploreAppSignalsResponse(),
        google=ExploreGoogleSignalsResponse(),
    )


def _origin_point(latitude: float | None, longitude: float | None):
    if latitude is None or longitude is None:
        return None
    return func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326).cast(
        Geography(geometry_type="POINT", srid=4326)
    )
