"""Public map endpoints / 公開地圖端點。"""

from __future__ import annotations

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import Settings, get_settings
from api.core.database import get_session
from api.domain.schemas import (
    MapCuisineResponse,
    MapRestaurantsResponse,
    MapSearchLocationResponse,
    MapSearchResponse,
    PriceRange,
)
from api.integrations.geocoding import GeocodingProvider, get_geocoding_provider
from api.services.map import (
    list_active_cuisines,
    query_public_restaurant_search,
    query_public_restaurants,
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
    del zoom  # Validated now and reserved for future server-side clustering rules.
    if west >= east or south >= north:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="map bounds must satisfy west < east and south < north",
        )

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
    return MapRestaurantsResponse(
        status="zoom_required" if zoom_required else "ok",
        restaurants=restaurants,
    )


@router.get("/cuisines", response_model=list[MapCuisineResponse])
async def list_public_cuisines(session: SessionDep) -> list[MapCuisineResponse]:
    """List enabled cuisines for public filters / 提供公開篩選的啟用料理分類。"""
    return await list_active_cuisines(session)


@router.get("/search", response_model=MapSearchResponse)
async def search_public_map(
    session: SessionDep,
    provider: Annotated[GeocodingProvider, Depends(get_geocoding_provider)],
    q: Annotated[str, Query(min_length=2, max_length=120)],
    limit: Annotated[int, Query(ge=1, le=5)] = 5,
) -> MapSearchResponse:
    """Search locations and published restaurants without mixing sources.

    分別搜尋地理位置與正式店家，避免外部地理編碼結果直接成為店家資料。
    """
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
    locations: list[MapSearchLocationResponse] = []
    provider_failed = False
    if provider.configured:
        try:
            locations = [
                MapSearchLocationResponse(
                    label=candidate.label,
                    latitude=candidate.latitude,
                    longitude=candidate.longitude,
                    source="geocoding",
                )
                for candidate in (await provider.geocode(q))[:limit]
            ]
        except httpx.HTTPError:
            provider_failed = True

    return MapSearchResponse(
        status="partial" if provider_failed else "ok",
        locations=locations,
        restaurants=restaurant_results,
    )
