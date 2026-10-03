"""Restaurant exploration queries / 餐廳探索查詢。"""

from __future__ import annotations

import re
import uuid
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import Select, func, or_, select
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
    ExploreSort,
    MapCuisineResponse,
    PriceRange,
)
from api.integrations.google_places import (
    GooglePlaceLookup,
    fetch_google_signals,
    fetch_google_signals_batch,
)
from api.services.ranking import rank_restaurants
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
    sort: ExploreSort = "recommended",
) -> ExploreRestaurantsResponse:
    """Search, score, and rank existing published restaurants / 搜尋並排序已發布店家。"""
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
        statement = statement.where(
            or_(
                func.lower(Restaurant.name).contains(query.casefold()),
                func.lower(Restaurant.address).contains(query.casefold()),
                _search_document_expression().op("@@")(func.websearch_to_tsquery("simple", query)),
                _normalized_address_expression().contains(_normalize_search_term(query)),
            )
        )
    if cuisine_ids:
        statement = statement.where(Restaurant.primary_cuisine_id.in_(cuisine_ids))
    if price_ranges:
        statement = statement.where(Restaurant.price_range.in_(price_ranges))
    rows = list((await session.execute(statement)).all())
    if origin is None:
        restaurants = [row[0] for row in rows]
        distances: dict[uuid.UUID, float | None] = {}
    else:
        restaurants = [row[0] for row in rows]
        distances = {row[0].id: float(row[1]) for row in rows}
    app_stats = await get_restaurant_app_stats(session, [item.id for item in restaurants])
    explore_items = [item for item in restaurants if _is_explore_ready(item)]
    enabled_items = [item for item in explore_items if item.google_lookup_enabled]
    google_signals = await fetch_google_signals_batch(
        [
            GooglePlaceLookup(
                place_id=item.google_place_id,
                name=item.name,
                address=item.address,
                latitude=item.latitude,
                longitude=item.longitude,
            )
            for item in enabled_items
        ]
    )
    google_by_restaurant_id = dict(
        zip((item.id for item in enabled_items), google_signals, strict=True)
    )
    ranked = rank_restaurants(
        explore_items,
        sort=sort,
        distances=distances,
        app_signals=app_stats,
        google_signals=google_by_restaurant_id,
        price_filter_active=bool(price_ranges),
    )
    responses = [
        _summary_response(
            item,
            distance_meters=distances.get(item.id),
            app_signals=app_stats.get(item.id),
            google_signals=google_by_restaurant_id.get(item.id),
        )
        for item in ranked
    ]
    return ExploreRestaurantsResponse(
        query=query,
        sort=sort,
        top_restaurants=responses[:3],
        restaurants=responses[:result_limit],
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
        google_signals=(
            await fetch_google_signals(
                place_id=restaurant.google_place_id,
                name=restaurant.name,
                address=restaurant.address,
                latitude=restaurant.latitude,
                longitude=restaurant.longitude,
            )
            if restaurant.google_lookup_enabled
            else None
        ),
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
    google_signals: ExploreGoogleSignalsResponse | None = None,
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
        google=google_signals or ExploreGoogleSignalsResponse(),
    )


def _origin_point(latitude: float | None, longitude: float | None):
    if latitude is None or longitude is None:
        return None
    return func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326).cast(
        Geography(geometry_type="POINT", srid=4326)
    )


def _search_document_expression():
    return func.to_tsvector(
        "simple",
        func.concat_ws(
            " ",
            func.coalesce(Restaurant.name, ""),
            func.coalesce(Restaurant.address, ""),
        ),
    )


def _normalized_address_expression():
    normalized = func.lower(Restaurant.address)
    for source, target in (
        ("台灣", ""),
        ("臺灣", ""),
        ("台", "臺"),
        ("巿", "市"),
        (" ", ""),
        (",", ""),
        ("，", ""),
        ("、", ""),
        (".", ""),
        ("．", ""),
        ("·", ""),
        ("-", ""),
        ("－", ""),
        ("—", ""),
    ):
        normalized = func.replace(normalized, source, target)
    return normalized


def _normalize_search_term(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = normalized.replace("台灣", "").replace("臺灣", "")
    normalized = normalized.replace("台", "臺").replace("巿", "市")
    return re.sub(r"[\s,，、.．·\-－—]", "", normalized)
