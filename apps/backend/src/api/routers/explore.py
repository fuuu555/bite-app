"""Restaurant exploration endpoints / 餐廳探索端點。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_session
from api.domain.schemas import (
    ExploreDistanceKm,
    ExploreRestaurantDetailResponse,
    ExploreRestaurantsResponse,
    ExploreSort,
    PriceRange,
)
from api.services.explore import get_explore_restaurant, query_explore_restaurants

router = APIRouter(prefix="/api/v1/explore", tags=["explore"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/restaurants", response_model=ExploreRestaurantsResponse)
async def search_explore_restaurants(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    cuisine_ids: Annotated[list[uuid.UUID] | None, Query()] = None,
    price_ranges: Annotated[list[PriceRange] | None, Query()] = None,
    latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
    distance_km: Annotated[ExploreDistanceKm | None, Query()] = None,
    sort: Annotated[ExploreSort, Query()] = "stable",
    limit: Annotated[int, Query(ge=1, le=50)] = 24,
) -> ExploreRestaurantsResponse:
    """Return one source for Top 3 and full results / 回傳 Top 3 與完整列表共用結果。"""
    query = q.strip() if q else None
    if query and len(query) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="search query must contain at least two non-whitespace characters",
        )
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="latitude and longitude must be provided together",
        )
    if distance_km is not None and latitude is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="distance filter requires latitude and longitude",
        )
    del sort  # Only the explicit stable skeleton strategy is currently available.
    return await query_explore_restaurants(
        session,
        query=query,
        cuisine_ids=cuisine_ids,
        price_ranges=price_ranges,
        latitude=latitude,
        longitude=longitude,
        distance_km=distance_km,
        result_limit=limit,
    )


@router.get(
    "/restaurants/{restaurant_id}",
    response_model=ExploreRestaurantDetailResponse,
)
async def explore_restaurant_detail(
    restaurant_id: uuid.UUID,
    session: SessionDep,
    latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> ExploreRestaurantDetailResponse:
    """Return one published restaurant or a public 404 / 只公開已發布店家。"""
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="latitude and longitude must be provided together",
        )
    restaurant = await get_explore_restaurant(
        session,
        restaurant_id,
        latitude=latitude,
        longitude=longitude,
    )
    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="published restaurant not found",
        )
    return restaurant
