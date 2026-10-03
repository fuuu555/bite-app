"""Public tourism open-data endpoints / 公開觀光開放資料端點。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import Settings, get_settings
from api.core.database import get_session
from api.domain.schemas import (
    TourismPlaceCategory,
    TourismPlacesResponse,
    TourismSourceDataset,
)
from api.services.tourism_data import query_tourism_places

router = APIRouter(prefix="/api/v1/tourism", tags=["tourism"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/places", response_model=TourismPlacesResponse)
async def list_tourism_places(
    session: SessionDep,
    settings: SettingsDep,
    west: Annotated[float, Query(ge=-180, le=180)],
    south: Annotated[float, Query(ge=-90, le=90)],
    east: Annotated[float, Query(ge=-180, le=180)],
    north: Annotated[float, Query(ge=-90, le=90)],
    categories: Annotated[list[TourismPlaceCategory] | None, Query()] = None,
    datasets: Annotated[list[TourismSourceDataset] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=250)] = 100,
) -> TourismPlacesResponse:
    """Return active official places inside one bounded viewport."""
    if west >= east or south >= north:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="tourism bounds must satisfy west < east and south < north",
        )

    places, has_more = await query_tourism_places(
        session,
        west=west,
        south=south,
        east=east,
        north=north,
        categories=categories,
        datasets=datasets,
        result_limit=min(limit, settings.public_map_result_limit),
    )
    return TourismPlacesResponse(places=places, has_more=has_more)
