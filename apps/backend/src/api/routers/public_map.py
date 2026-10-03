"""Public map endpoints / 公開地圖端點。"""

from __future__ import annotations

import uuid
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import Settings, get_settings
from api.core.database import get_session
from api.domain.schemas import (
    MapCuisineResponse,
    MapRestaurantsResponse,
    MapSearchResponse,
    PriceRange,
)
from api.services.map import (
    list_active_cuisines,
    query_public_restaurant_search,
    query_public_restaurants,
)
from api.services.map_observability import (
    MapQueryCacheKey,
    map_performance_monitor,
    map_query_cache,
)

router = APIRouter(prefix="/api/v1/map", tags=["map"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/restaurants", response_model=MapRestaurantsResponse)
async def list_public_restaurants(
    session: SessionDep,
    settings: SettingsDep,
    west: Annotated[float, Query(ge=-180, le=180)],
    south: Annotated[float, Query(ge=-90, le=90)],
    east: Annotated[float, Query(ge=-180, le=180)],
    north: Annotated[float, Query(ge=-90, le=90)],
    zoom: Annotated[float, Query(ge=0, le=24)],
    city: Annotated[str | None, Query(min_length=1, max_length=40)] = None,
    district: Annotated[str | None, Query(min_length=1, max_length=40)] = None,
    cuisine_ids: Annotated[list[uuid.UUID] | None, Query()] = None,
    price_ranges: Annotated[list[PriceRange] | None, Query()] = None,
) -> MapRestaurantsResponse:
    """Query one viewport without exposing the complete restaurant table.

    只查詢一個可視範圍，禁止以無邊界請求取得全部店家。
    """
    if west >= east or south >= north:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="map bounds must satisfy west < east and south < north",
        )

    started_at = perf_counter()
    cache_key = MapQueryCacheKey(
        west=west,
        south=south,
        east=east,
        north=north,
        zoom=zoom,
        city=city.strip().lower() if city else None,
        district=district.strip().lower() if district else None,
        cuisine_ids=tuple(sorted(str(item) for item in cuisine_ids or [])),
        price_ranges=tuple(sorted(str(item) for item in price_ranges or [])),
        result_limit=settings.public_map_result_limit,
    )
    query_summary = _map_query_summary(
        west=west,
        south=south,
        east=east,
        north=north,
        zoom=zoom,
        city=city,
        district=district,
        cuisine_ids=cuisine_ids,
        price_ranges=price_ranges,
    )
    cached_response = map_query_cache.get(cache_key)
    cache_hit = cached_response is not None
    try:
        if cached_response is not None:
            response = cached_response
        else:
            restaurants, zoom_required = await query_public_restaurants(
                session,
                west=west,
                south=south,
                east=east,
                north=north,
                cuisine_ids=cuisine_ids,
                price_ranges=price_ranges,
                city=city,
                district=district,
                result_limit=settings.public_map_result_limit,
            )
            response = MapRestaurantsResponse(
                status="zoom_required" if zoom_required else "ok",
                restaurants=restaurants,
            )
            map_query_cache.set(cache_key, response)
    except Exception:
        map_performance_monitor.record(
            duration_ms=(perf_counter() - started_at) * 1000,
            result_count=0,
            cache_hit=cache_hit,
            response_status="error",
            query_summary=query_summary,
        )
        raise

    map_performance_monitor.record(
        duration_ms=(perf_counter() - started_at) * 1000,
        result_count=len(response.restaurants),
        cache_hit=cache_hit,
        response_status=response.status,
        query_summary=query_summary,
    )
    return response


def _map_query_summary(
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    zoom: float,
    city: str | None,
    district: str | None,
    cuisine_ids: list[uuid.UUID] | None,
    price_ranges: list[PriceRange] | None,
) -> str:
    filters = [
        f"city={city}" if city else None,
        f"district={district}" if district else None,
        f"cuisines={len(cuisine_ids or [])}" if cuisine_ids else None,
        f"prices={len(price_ranges or [])}" if price_ranges else None,
    ]
    filter_summary = ", ".join(item for item in filters if item) or "none"
    return (
        f"zoom={zoom:g}; bounds={west:.3f},{south:.3f},{east:.3f},{north:.3f}; "
        f"filters={filter_summary}"
    )


@router.get("/cuisines", response_model=list[MapCuisineResponse])
async def list_public_cuisines(session: SessionDep) -> list[MapCuisineResponse]:
    """List enabled cuisines for public filters / 提供公開篩選的啟用料理分類。"""
    return await list_active_cuisines(session)


@router.get("/search", response_model=MapSearchResponse)
async def search_public_map(
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, max_length=120)],
    limit: Annotated[int, Query(ge=1, le=5)] = 5,
) -> MapSearchResponse:
    """Search only published restaurants / 只搜尋已發布店家。"""
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="search query must contain at least two non-whitespace characters",
        )

    restaurant_results = await query_public_restaurant_search(
        session,
        query=q,
        result_limit=limit,
    )
    return MapSearchResponse(
        status="ok",
        restaurants=restaurant_results,
    )
