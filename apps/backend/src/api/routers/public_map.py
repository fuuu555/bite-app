"""Public Stage 2 map endpoints / Stage 2 公開地圖端點。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import Settings, get_settings
from api.db import get_session
from api.map_service import query_public_restaurants
from api.schemas import MapRestaurantsResponse, PriceRange

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
        result_limit=settings.public_map_result_limit,
    )
    return MapRestaurantsResponse(
        status="zoom_required" if zoom_required else "ok",
        restaurants=restaurants,
    )
