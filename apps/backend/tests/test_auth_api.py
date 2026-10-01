"""Google user account integration tests / Google 一般使用者登入整合測試。"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from api.core.config import get_settings
from api.core.database import session_factory
from api.core.security import create_user_session, hash_password
from api.domain.models import User
from api.integrations.google_oauth import GoogleIdentity
from api.main import app
from api.routers import auth as auth_router

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostGIS running",
)


@pytest.mark.asyncio
async def test_google_login_creates_profile_session_and_logout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unique = uuid.uuid4().hex
    email = f"google-user-{unique}@example.test"
    provider_subject = f"google-sub-{unique}"
    user_id: uuid.UUID | None = None
    other_user_id: uuid.UUID | None = None
    other_session_id: uuid.UUID | None = None

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    get_settings.cache_clear()

    async def fake_exchange(code: str, code_verifier: str) -> GoogleIdentity:
        assert code == "authorization-code"
        assert code_verifier
        return GoogleIdentity(
            provider_subject=provider_subject,
            email=email,
            email_verified=True,
            display_name="Google 測試使用者",
            avatar_url="https://example.test/avatar.png",
        )

    monkeypatch.setattr(auth_router, "exchange_google_code", fake_exchange)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            start = await client.get("/api/v1/auth/google/start", follow_redirects=False)
            assert start.status_code == 303
            assert "accounts.google.com" in start.headers["location"]
            state = client.cookies.get("bitemap_google_state")
            assert state

            callback = await client.get(
                "/api/v1/auth/google/callback",
                params={"code": "authorization-code", "state": state},
                follow_redirects=False,
            )
            assert callback.status_code == 303
            assert callback.headers["location"].endswith("/profile")
            assert "bitemap_user_session" in client.cookies

            current = await client.get("/api/v1/auth/me")
            assert current.status_code == 200
            user_id = uuid.UUID(current.json()["id"])
            assert current.json()["email"] == email

            profile = await client.get("/api/v1/me/profile")
            assert profile.status_code == 200
            assert profile.json()["display_name"] == "Google 測試使用者"
            assert profile.json()["avatar_url"] == "https://example.test/avatar.png"

            public = await client.get(f"/api/v1/profiles/{user_id}")
            assert public.status_code == 200
            assert "email" not in public.json()

            async with session_factory() as session:
                other_user = User(
                    email=f"other-user-{unique}@example.test",
                    password_hash=None,
                    role="user",
                    is_active=True,
                )
                session.add(other_user)
                await session.flush()
                other_session, _ = await create_user_session(session, other_user, "其他裝置")
                other_user_id = other_user.id
                other_session_id = other_session.id

            assert (
                await client.delete(f"/api/v1/me/sessions/{other_session_id}")
            ).status_code == 404

            refreshed = await client.post("/api/v1/auth/session/refresh")
            assert refreshed.status_code == 200
            assert (await client.get("/api/v1/admin/restaurants")).status_code == 401

            logged_out = await client.delete("/api/v1/auth/session")
            assert logged_out.status_code == 204
            assert (await client.get("/api/v1/auth/me")).status_code == 401
    finally:
        if user_id:
            async with session_factory() as session:
                await session.execute(delete(User).where(User.id == user_id))
                if other_user_id:
                    await session.execute(delete(User).where(User.id == other_user_id))
                await session.commit()
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_google_user_can_share_admin_email_without_changing_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unique = uuid.uuid4().hex
    email = f"overlap-user-{unique}@example.test"
    provider_subject = f"google-overlap-{unique}"
    admin_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    get_settings.cache_clear()

    async def fake_exchange(code: str, code_verifier: str) -> GoogleIdentity:
        assert code == "authorization-code"
        assert code_verifier
        return GoogleIdentity(
            provider_subject=provider_subject,
            email=email,
            email_verified=True,
            display_name="重疊 email 使用者",
            avatar_url=None,
        )

    monkeypatch.setattr(auth_router, "exchange_google_code", fake_exchange)
    try:
        async with session_factory() as session:
            admin = User(
                email=email,
                password_hash=hash_password("admin-overlap-password"),
                role="admin",
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            admin_id = admin.id

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            start = await client.get("/api/v1/auth/google/start", follow_redirects=False)
            state = client.cookies.get("bitemap_google_state")
            assert start.status_code == 303
            assert state
            callback = await client.get(
                "/api/v1/auth/google/callback",
                params={"code": "authorization-code", "state": state},
                follow_redirects=False,
            )
            assert callback.status_code == 303
            current = await client.get("/api/v1/auth/me")
            assert current.status_code == 200
            user_id = uuid.UUID(current.json()["id"])
            assert current.json()["role"] == "user"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as admin_client:
            admin_login = await admin_client.post(
                "/api/v1/admin/session",
                json={"email": email, "password": "admin-overlap-password"},
            )
            assert admin_login.status_code == 200
            assert admin_login.json()["role"] == "admin"
    finally:
        async with session_factory() as session:
            if user_id:
                await session.execute(delete(User).where(User.id == user_id))
            if admin_id:
                await session.execute(delete(User).where(User.id == admin_id))
            await session.commit()
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_google_login_reuses_existing_provider_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unique = uuid.uuid4().hex
    email = f"subject-user-{unique}@example.test"
    provider_subject = f"google-subject-{unique}"
    user_id: uuid.UUID | None = None

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    get_settings.cache_clear()

    async def fake_exchange(code: str, code_verifier: str) -> GoogleIdentity:
        return GoogleIdentity(
            provider_subject=provider_subject,
            email=email,
            email_verified=True,
            display_name="重複 subject 使用者",
            avatar_url=None,
        )

    monkeypatch.setattr(auth_router, "exchange_google_code", fake_exchange)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as first_client:
            start = await first_client.get("/api/v1/auth/google/start", follow_redirects=False)
            state = first_client.cookies.get("bitemap_google_state")
            assert start.status_code == 303
            assert state
            first_callback = await first_client.get(
                "/api/v1/auth/google/callback",
                params={"code": "authorization-code", "state": state},
                follow_redirects=False,
            )
            assert first_callback.status_code == 303
            user_id = uuid.UUID((await first_client.get("/api/v1/auth/me")).json()["id"])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as second_client:
            start = await second_client.get("/api/v1/auth/google/start", follow_redirects=False)
            state = second_client.cookies.get("bitemap_google_state")
            assert start.status_code == 303
            assert state
            second_callback = await second_client.get(
                "/api/v1/auth/google/callback",
                params={"code": "authorization-code", "state": state},
                follow_redirects=False,
            )
            assert second_callback.status_code == 303
            assert uuid.UUID((await second_client.get("/api/v1/auth/me")).json()["id"]) == user_id
    finally:
        if user_id:
            async with session_factory() as session:
                await session.execute(delete(User).where(User.id == user_id))
                await session.commit()
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_google_login_reports_general_user_email_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unique = uuid.uuid4().hex
    email = f"conflict-user-{unique}@example.test"
    existing_id: uuid.UUID | None = None

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    get_settings.cache_clear()

    async def fake_exchange(code: str, code_verifier: str) -> GoogleIdentity:
        return GoogleIdentity(
            provider_subject=f"google-conflict-{unique}",
            email=email,
            email_verified=True,
            display_name="衝突使用者",
            avatar_url=None,
        )

    monkeypatch.setattr(auth_router, "exchange_google_code", fake_exchange)
    try:
        async with session_factory() as session:
            existing = User(email=email, password_hash=None, role="user", is_active=True)
            session.add(existing)
            await session.commit()
            existing_id = existing.id

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            start = await client.get("/api/v1/auth/google/start", follow_redirects=False)
            state = client.cookies.get("bitemap_google_state")
            assert start.status_code == 303
            assert state
            callback = await client.get(
                "/api/v1/auth/google/callback",
                params={"code": "authorization-code", "state": state},
                follow_redirects=False,
            )
            assert callback.status_code == 303
            assert callback.headers["location"].endswith("/login?error=account_conflict")
    finally:
        if existing_id:
            async with session_factory() as session:
                await session.execute(delete(User).where(User.id == existing_id))
                await session.commit()
        get_settings.cache_clear()
