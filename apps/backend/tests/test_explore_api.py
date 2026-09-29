"""Exploration API integration tests / 探索 API 整合測試。"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from api.core.database import session_factory
from api.domain.models import Cuisine, Restaurant, RestaurantMenu, RestaurantPhoto
from api.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)


@pytest.mark.asyncio
async def test_explore_search_and_detail_share_published_restaurants() -> None:
    """Top 3, full results, and detail use the same published restaurant source."""
    unique = uuid.uuid4().hex
    cuisine_id = uuid.uuid4()
    restaurant_ids = [uuid.uuid4() for _ in range(3)]

    async with session_factory() as session:
        session.add(
            Cuisine(
                id=cuisine_id,
                slug=f"explore-{unique}",
                display_name="探索測試料理",
                color="#F26B4F",
                icon_key="rice-bowl",
                is_active=True,
            )
        )
        session.add_all(
            [
                Restaurant(
                    id=restaurant_ids[0],
                    name="Alpha 探索拉麵",
                    address="桃園市中壢區測試路 1 號",
                    menu_url="https://example.test/menu",
                    primary_cuisine_id=cuisine_id,
                    price_range="200_to_400",
                    status="published",
                    source_type="manual",
                    latitude=24.9537,
                    longitude=121.2258,
                ),
                Restaurant(
                    id=restaurant_ids[1],
                    name="Beta 探索拉麵",
                    address="桃園市中壢區測試路 2 號",
                    primary_cuisine_id=cuisine_id,
                    price_range="under_200",
                    status="published",
                    source_type="manual",
                    latitude=24.958,
                    longitude=121.23,
                ),
                Restaurant(
                    id=restaurant_ids[2],
                    name="草稿探索拉麵",
                    address="桃園市中壢區測試路 3 號",
                    primary_cuisine_id=cuisine_id,
                    price_range="under_200",
                    status="draft",
                    source_type="manual",
                    latitude=24.955,
                    longitude=121.228,
                ),
            ]
        )
        session.add(
            RestaurantMenu(
                restaurant_id=restaurant_ids[0],
                title="官方菜單",
                url="https://example.test/menu-v2",
                last_updated_at=None,
            )
        )
        session.add(
            RestaurantPhoto(
                restaurant_id=restaurant_ids[0],
                url="https://example.test/photo.jpg",
                alt_text="店家門面",
                sort_order=0,
            )
        )
        await session.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/api/v1/explore/restaurants",
                params={"q": "探索拉麵", "cuisine_ids": str(cuisine_id)},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["sort"] == "stable"
            assert [item["name"] for item in payload["restaurants"]] == [
                "Alpha 探索拉麵",
                "Beta 探索拉麵",
            ]
            assert payload["top_restaurants"] == payload["restaurants"]
            assert payload["restaurants"][0]["app"]["revisit_rate"] is None
            assert payload["restaurants"][0]["google"]["rating"] is None
            assert payload["restaurants"][0]["photo_url"] == "https://example.test/photo.jpg"

            detail = await client.get(f"/api/v1/explore/restaurants/{restaurant_ids[0]}")
            assert detail.status_code == 200
            assert detail.json()["name"] == "Alpha 探索拉麵"
            assert detail.json()["menu"] == {
                "url": "https://example.test/menu",
                "last_updated_at": None,
            }
            assert detail.json()["menus"][0]["title"] == "官方菜單"
            assert detail.json()["photos"][0]["alt_text"] == "店家門面"

            draft = await client.get(f"/api/v1/explore/restaurants/{restaurant_ids[2]}")
            assert draft.status_code == 404
    finally:
        async with session_factory() as session:
            await session.execute(delete(Restaurant).where(Restaurant.id.in_(restaurant_ids)))
            await session.execute(delete(Cuisine).where(Cuisine.id == cuisine_id))
            await session.commit()
