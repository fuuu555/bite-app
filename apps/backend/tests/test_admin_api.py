"""Stage 1 administration integration tests / Stage 1 管理 API 整合測試。"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text

from api.db import session_factory
from api.geocoding import get_geocoding_provider
from api.main import app
from api.models import AdminSession, AuditLog, AuditLogChange, Cuisine, Restaurant, User
from api.schemas import GeocodingCandidate
from api.security import hash_password

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)


@pytest.mark.asyncio
async def test_admin_restaurant_publish_flow_and_postgis_round_trip() -> None:
    """Unauthorized callers are denied and publish enforces complete map data.

    未授權呼叫會被拒絕，發布時也會檢查完整地圖資料。
    """
    unique = uuid.uuid4().hex
    email = f"stage1-{unique}@example.test"
    password = "stage1-test-password"
    user_id: uuid.UUID | None = None
    cuisine_id: uuid.UUID | None = None
    restaurant_id: uuid.UUID | None = None

    class FakeGeocodingProvider:
        configured = True

        async def geocode(self, address: str) -> list[GeocodingCandidate]:
            del address
            return [GeocodingCandidate(label="測試地址", latitude=25.0, longitude=121.0)]

        async def reverse(self, latitude: float, longitude: float) -> str:
            del latitude, longitude
            return "測試地址"

    app.dependency_overrides[get_geocoding_provider] = FakeGeocodingProvider

    async with session_factory() as session:
        user = User(
            email=email,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        user_id = user.id

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            denied = await client.get("/api/v1/admin/restaurants")
            assert denied.status_code == 401

            login = await client.post(
                "/api/v1/admin/session",
                json={"email": email, "password": password},
            )
            assert login.status_code == 200
            assert login.json()["role"] == "admin"

            cuisine = await client.post(
                "/api/v1/admin/cuisines",
                json={
                    "slug": f"taiwanese-{unique}",
                    "display_name": "台灣料理",
                    "color": "#F26B4F",
                    "icon_key": "rice-bowl",
                },
            )
            assert cuisine.status_code == 201
            cuisine_id = uuid.UUID(cuisine.json()["id"])

            created = await client.post(
                "/api/v1/admin/restaurants",
                json={"name": "Stage 1 測試店", "address": "台北市測試路 1 號"},
            )
            assert created.status_code == 201
            restaurant_id = uuid.UUID(created.json()["id"])
            assert created.json()["status"] == "draft"

            incomplete = await client.post(f"/api/v1/admin/restaurants/{restaurant_id}/publish")
            assert incomplete.status_code == 422
            assert set(incomplete.json()["detail"]["missing"]) == {
                "coordinates",
                "primary_cuisine",
                "price_range",
            }

            updated = await client.patch(
                f"/api/v1/admin/restaurants/{restaurant_id}",
                json={
                    "primary_cuisine_id": str(cuisine_id),
                    "price_range": "200_to_400",
                    "menu_url": "https://example.test/menu/stage1",
                    "latitude": 25.0478,
                    "longitude": 121.5319,
                },
            )
            assert updated.status_code == 200
            assert updated.json()["menu_url"] == "https://example.test/menu/stage1"

            published = await client.post(f"/api/v1/admin/restaurants/{restaurant_id}/publish")
            assert published.status_code == 200
            assert published.json()["status"] == "published"

            archived = await client.post(f"/api/v1/admin/restaurants/{restaurant_id}/archive")
            assert archived.status_code == 200
            assert archived.json()["status"] == "archived"

            geocode = await client.post("/api/v1/admin/geocode", json={"address": "台北車站"})
            assert geocode.status_code == 200
            assert geocode.json()["candidates"][0]["label"] == "測試地址"

        async with session_factory() as session:
            coordinates = (
                await session.execute(
                    text(
                        "SELECT ST_Y(location::geometry), ST_X(location::geometry) "
                        "FROM restaurants WHERE id = :restaurant_id"
                    ),
                    {"restaurant_id": restaurant_id},
                )
            ).one()
            assert coordinates[0] == pytest.approx(25.0478)
            assert coordinates[1] == pytest.approx(121.5319)

            audit_changes = set(
                (
                    await session.execute(
                        select(AuditLog.action, AuditLogChange.field_name)
                        .join(AuditLogChange)
                        .where(AuditLog.entity_id == restaurant_id)
                    )
                ).all()
            )
            assert ("published", "status") in audit_changes
            assert ("archived", "status") in audit_changes
    finally:
        app.dependency_overrides.pop(get_geocoding_provider, None)
        async with session_factory() as session:
            if restaurant_id:
                audit_log_ids = select(AuditLog.id).where(AuditLog.entity_id == restaurant_id)
                await session.execute(
                    delete(AuditLogChange).where(AuditLogChange.audit_log_id.in_(audit_log_ids))
                )
                await session.execute(delete(AuditLog).where(AuditLog.entity_id == restaurant_id))
                await session.execute(delete(Restaurant).where(Restaurant.id == restaurant_id))
            if cuisine_id:
                await session.execute(delete(Cuisine).where(Cuisine.id == cuisine_id))
            if user_id:
                session_ids = select(AdminSession.id).where(AdminSession.user_id == user_id)
                await session.execute(delete(AdminSession).where(AdminSession.id.in_(session_ids)))
                audit_log_ids = select(AuditLog.id).where(AuditLog.actor_user_id == user_id)
                await session.execute(
                    delete(AuditLogChange).where(AuditLogChange.audit_log_id.in_(audit_log_ids))
                )
                await session.execute(delete(AuditLog).where(AuditLog.actor_user_id == user_id))
                await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
