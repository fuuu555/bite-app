from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import delete

from api.core.config import get_settings
from api.core.database import session_factory
from api.domain.models import Cuisine, Restaurant, TourismSourcePlace
from api.domain.schemas import ItineraryPlanRequest
from api.services.itinerary import parse_rules_prompt, plan_itinerary


def test_rules_prompt_extracts_city_preferences_and_lodging() -> None:
    intent = parse_rules_prompt(
        "我在花蓮，明天想安排一日自然景點，中午吃素，晚上住附近，不開車",
        None,
    )

    assert intent.city == "花蓮縣"
    assert intent.duration == "full_day"
    assert intent.transport == "public_transport"
    assert "自然" in intent.interests
    assert intent.meal_preference == "素食"
    assert intent.include_lodging is True


def test_plan_request_requires_coordinates_or_city() -> None:
    with pytest.raises(ValueError, match="latitude and longitude or city"):
        ItineraryPlanRequest(quick_action="eat")


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)
async def test_stay_quick_action_only_uses_official_hotel_records() -> None:
    token = uuid.uuid4().hex[:12]
    cuisine = Cuisine(
        slug=f"itinerary-test-{token}",
        display_name=f"行程測試料理 {token}",
        color="#F26B4F",
        icon_key="tools-kitchen-3",
    )
    restaurant = Restaurant(
        name=f"行程測試餐廳 {token}",
        address="台北市中正區測試路 1 號",
        primary_cuisine=cuisine,
        price_range="under_200",
        status="published",
        google_lookup_enabled=False,
        latitude=25.0375,
        longitude=121.5637,
    )
    hotel = TourismSourcePlace(
        source_dataset="hotel",
        source_record_id=f"hotel-{token}",
        category="hotel",
        name=f"行程測試旅館 {token}",
        address="台北市中正區測試路 2 號",
        latitude=25.0380,
        longitude=121.5640,
        content_hash="a" * 64,
        raw_payload={},
    )
    food = TourismSourcePlace(
        source_dataset="food",
        source_record_id=f"food-{token}",
        category="restaurant",
        name=f"行程測試官方餐廳 {token}",
        address="台北市中正區測試路 3 號",
        latitude=25.0381,
        longitude=121.5641,
        content_hash="b" * 64,
        raw_payload={},
    )

    async with session_factory() as session:
        session.add_all([cuisine, restaurant, hotel, food])
        await session.commit()
        try:
            result = await plan_itinerary(
                session,
                ItineraryPlanRequest(
                    latitude=25.0375,
                    longitude=121.5637,
                    quick_action="stay",
                    radius_km=2,
                ),
                settings=get_settings(),
            )
            assert result.stops
            assert all(stop.role == "lodging" for stop in result.stops)
            assert all(stop.place.source_dataset == "hotel" for stop in result.stops)
            assert all(stop.place.source == "tourism" for stop in result.stops)
        finally:
            await session.execute(
                delete(TourismSourcePlace).where(
                    TourismSourcePlace.id.in_([hotel.id, food.id])
                )
            )
            await session.execute(delete(Restaurant).where(Restaurant.id == restaurant.id))
            await session.execute(delete(Cuisine).where(Cuisine.id == cuisine.id))
            await session.commit()
