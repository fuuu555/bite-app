"""Personalized itinerary endpoints / 個人化旅遊行程端點。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import Settings, get_settings
from api.core.database import get_session
from api.domain.schemas import ItineraryPlanRequest, ItineraryPlanResponse
from api.services.itinerary import plan_itinerary

router = APIRouter(prefix="/api/v1/itinerary", tags=["itinerary"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post("/plan", response_model=ItineraryPlanResponse)
async def create_itinerary_plan(
    payload: ItineraryPlanRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> ItineraryPlanResponse:
    """Recommend grounded nearby places and compose a small travel plan."""
    return await plan_itinerary(session, payload, settings=settings)
