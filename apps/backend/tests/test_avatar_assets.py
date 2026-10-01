"""Local avatar asset integration tests / 本地頭貼資產整合測試。"""

from __future__ import annotations

import base64
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from api.core.database import session_factory
from api.core.security import create_user_session, hash_password
from api.domain.models import AdminSession, AvatarAsset, User, UserProfile, UserSession
from api.main import app
from api.services.avatar_assets import avatar_file_for_asset

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)

ONE_BY_ONE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@pytest.mark.asyncio
async def test_admin_uploads_and_user_selects_local_avatar() -> None:
    unique = uuid.uuid4().hex
    admin_id = uuid.uuid4()
    user_id = uuid.uuid4()
    asset_id: uuid.UUID | None = None
    admin_password = "avatar-admin-password"

    async with session_factory() as session:
        admin = User(
            id=admin_id,
            email=f"avatar-admin-{unique}@example.test",
            password_hash=hash_password(admin_password),
            role="admin",
            is_active=True,
        )
        user = User(
            id=user_id,
            email=f"avatar-user-{unique}@example.test",
            password_hash=None,
            role="user",
            is_active=True,
        )
        session.add_all(
            [
                admin,
                user,
                UserProfile(user_id=user_id, display_name="頭貼測試使用者"),
            ]
        )
        await session.flush()
        _, user_token = await create_user_session(session, user, "頭貼測試瀏覽器")
        await session.commit()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as admin_client:
            login = await admin_client.post(
                "/api/v1/admin/session",
                json={
                    "email": f"avatar-admin-{unique}@example.test",
                    "password": admin_password,
                },
            )
            assert login.status_code == 200

            uploaded = await admin_client.post(
                "/api/v1/admin/avatar-assets",
                data={"display_name": "測試海邊頭貼"},
                files={"file": ("avatar.png", ONE_BY_ONE_PNG, "image/png")},
            )
            assert uploaded.status_code == 201
            asset_id = uuid.UUID(uploaded.json()["id"])
            assert uploaded.json()["url"].startswith("/media/avatars/")

            disabled = await admin_client.patch(
                f"/api/v1/admin/avatar-assets/{asset_id}",
                json={"is_active": False},
            )
            assert disabled.status_code == 200

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as user_client:
            user_client.cookies.set("bitemap_user_session", user_token)
            hidden = await user_client.get("/api/v1/avatar-assets")
            assert hidden.status_code == 200
            assert all(item["id"] != str(asset_id) for item in hidden.json())

            rejected = await user_client.patch(
                "/api/v1/me/profile",
                json={"avatar_asset_id": str(asset_id)},
            )
            assert rejected.status_code == 422

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as admin_client:
            login = await admin_client.post(
                "/api/v1/admin/session",
                json={
                    "email": f"avatar-admin-{unique}@example.test",
                    "password": admin_password,
                },
            )
            assert login.status_code == 200
            enabled = await admin_client.patch(
                f"/api/v1/admin/avatar-assets/{asset_id}",
                json={"is_active": True},
            )
            assert enabled.status_code == 200

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as user_client:
            user_client.cookies.set("bitemap_user_session", user_token)
            available = await user_client.get("/api/v1/avatar-assets")
            assert available.status_code == 200
            assert any(item["id"] == str(asset_id) for item in available.json())

            selected = await user_client.patch(
                "/api/v1/me/profile",
                json={"avatar_asset_id": str(asset_id), "avatar_url": None},
            )
            assert selected.status_code == 200
            assert selected.json()["avatar_source"] == "builtin"
            assert selected.json()["avatar_asset_id"] == str(asset_id)
            media = await user_client.get(selected.json()["avatar_url"])
            assert media.status_code == 200
            assert media.content == ONE_BY_ONE_PNG
    finally:
        async with session_factory() as session:
            asset = await session.get(AvatarAsset, asset_id) if asset_id else None
            if asset is not None:
                avatar_path = avatar_file_for_asset(asset)
                await session.delete(asset)
                await session.flush()
                avatar_path.unlink(missing_ok=True)
            await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
            await session.execute(delete(AdminSession).where(AdminSession.user_id == admin_id))
            await session.execute(delete(User).where(User.id.in_([admin_id, user_id])))
            await session.commit()
