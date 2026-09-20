"""Stage 2 public map integration tests / Stage 2 公開地圖整合測試。"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from api.core.config import get_settings
from api.core.database import session_factory
from api.domain.models import Cuisine, Restaurant
from api.domain.schemas import GeocodingCandidate
from api.integrations.geocoding import get_geocoding_provider
from api.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)


class FakeGeocodingProvider:
    """Deterministic geocoder for API tests / API 測試使用的固定地理編碼器。"""

    configured = True

    async def geocode(self, address: str) -> list[GeocodingCandidate]:
        return [
            GeocodingCandidate(
                label=f"{address} 測試位置",
                latitude=24.9537,
                longitude=121.2258,
            )
        ]

    async def reverse(self, latitude: float, longitude: float) -> str | None:
        del latitude, longitude
        return None


@pytest.mark.asyncio
async def test_public_map_returns_only_published_restaurants_inside_bounds() -> None:
    """Bounds, publication state, filters, and limits are enforced together.

    同時驗證地圖邊界、發布狀態、篩選條件與結果上限。
    """
    unique = uuid.uuid4().hex
    cuisine_id = uuid.uuid4()
    restaurant_ids = [uuid.uuid4() for _ in range(4)]

    async with session_factory() as session:
        session.add(
            Cuisine(
                id=cuisine_id,
                slug=f"map-{unique}",
                display_name="地圖測試料理",
                color="#F26B4F",
                icon_key="rice-bowl",
                is_active=True,
            )
        )
        session.add_all(
            [
                Restaurant(
                    id=restaurant_ids[0],
                    name="範圍內已發布店家",
                    address="桃園市中壢區測試路 1 號",
                    primary_cuisine_id=cuisine_id,
                    price_range="under_200",
                    status="published",
                    source_type="manual",
                    latitude=24.9537,
                    longitude=121.2258,
                ),
                Restaurant(
                    id=restaurant_ids[1],
                    name="範圍內第二間已發布店家",
                    address="桃園市中壢區測試路 2 號",
                    primary_cuisine_id=cuisine_id,
                    price_range="200_to_400",
                    status="published",
                    source_type="manual",
                    latitude=24.958,
                    longitude=121.23,
                ),
                Restaurant(
                    id=restaurant_ids[2],
                    name="範圍內草稿店家",
                    address="桃園市中壢區測試路 3 號",
                    primary_cuisine_id=cuisine_id,
                    price_range="under_200",
                    status="draft",
                    source_type="manual",
                    latitude=24.955,
                    longitude=121.228,
                ),
                Restaurant(
                    id=restaurant_ids[3],
                    name="範圍外已發布店家",
                    address="台北市測試路 4 號",
                    primary_cuisine_id=cuisine_id,
                    price_range="under_200",
                    status="published",
                    source_type="manual",
                    latitude=25.0478,
                    longitude=121.5319,
                ),
            ]
        )
        await session.commit()

    query = {
        "west": 121.18,
        "south": 24.9,
        "east": 121.28,
        "north": 25.0,
        "zoom": 13,
        "cuisine_ids": str(cuisine_id),
    }
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/api/v1/map/restaurants", params=query)
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            assert {item["name"] for item in response.json()["restaurants"]} == {
                "範圍內已發布店家",
                "範圍內第二間已發布店家",
            }

            filtered = await client.get(
                "/api/v1/map/restaurants",
                params={**query, "price_ranges": "under_200"},
            )
            assert filtered.status_code == 200
            assert [item["name"] for item in filtered.json()["restaurants"]] == [
                "範圍內已發布店家"
            ]

            region_filtered = await client.get(
                "/api/v1/map/restaurants",
                params={**query, "city": "桃園市", "district": "中壢區"},
            )
            assert region_filtered.status_code == 200
            assert {item["name"] for item in region_filtered.json()["restaurants"]} == {
                "範圍內已發布店家",
                "範圍內第二間已發布店家",
            }

            app.dependency_overrides[get_geocoding_provider] = lambda: FakeGeocodingProvider()
            search_response = await client.get(
                "/api/v1/map/search",
                params={"q": "範圍內", "limit": 5},
            )
            assert search_response.status_code == 200
            assert search_response.json()["status"] == "ok"
            assert {item["name"] for item in search_response.json()["restaurants"]} == {
                "範圍內第二間已發布店家",
                "範圍內已發布店家",
            }

            location_response = await client.get(
                "/api/v1/map/search",
                params={"q": "中原大學", "limit": 5},
            )
            assert location_response.status_code == 200
            assert location_response.json()["locations"][0]["source"] == "geocoding"

            cuisines_response = await client.get("/api/v1/map/cuisines")
            assert cuisines_response.status_code == 200
            assert cuisines_response.json()[0]["id"] == str(cuisine_id)

            invalid_bounds = await client.get(
                "/api/v1/map/restaurants",
                params={**query, "west": 121.3, "east": 121.2},
            )
            assert invalid_bounds.status_code == 422

            limited_settings = get_settings().model_copy(update={"public_map_result_limit": 1})
            app.dependency_overrides[get_settings] = lambda: limited_settings
            limited = await client.get("/api/v1/map/restaurants", params=query)
            assert limited.status_code == 200
            assert limited.json() == {"status": "zoom_required", "restaurants": []}
    finally:
        app.dependency_overrides.pop(get_settings, None)
        app.dependency_overrides.pop(get_geocoding_provider, None)
        async with session_factory() as session:
            await session.execute(delete(Restaurant).where(Restaurant.id.in_(restaurant_ids)))
            await session.execute(delete(Cuisine).where(Cuisine.id == cuisine_id))
            await session.commit()
