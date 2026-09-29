"""Administrator authentication and authorization / 管理員驗證與授權。"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.core.database import get_session
from api.domain.models import AdminSession, User, UserSession

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password with Argon2id / 使用 Argon2id 雜湊密碼。"""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify without exposing hash failures / 驗證密碼且不洩漏雜湊錯誤。"""
    if not password_hash:
        return False
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_session_token(token: str) -> str:
    """Store only a one-way session token digest / 資料庫只保存 Session Token 摘要。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_admin_session(session: AsyncSession, user: User) -> str:
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    session.add(
        AdminSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(UTC) + timedelta(hours=settings.admin_session_hours),
        )
    )
    await session.commit()
    return token


def set_admin_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.admin_session_cookie,
        value=token,
        max_age=settings.admin_session_hours * 60 * 60,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


async def require_admin(
    session: Annotated[AsyncSession, Depends(get_session)],
    session_token: Annotated[str | None, Cookie(alias="bitemap_admin_session")] = None,
) -> User:
    """Deny by default unless a live admin session exists / 預設拒絕，僅接受有效管理員 Session。"""
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin authentication required",
        )

    result = await session.execute(
        select(AdminSession, User)
        .join(User, User.id == AdminSession.user_id)
        .where(
            AdminSession.token_hash == hash_session_token(session_token),
            AdminSession.expires_at > datetime.now(UTC),
            User.is_active.is_(True),
            User.role == "admin",
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin authentication required",
        )
    return row[1]


async def revoke_admin_session(session: AsyncSession, token: str | None) -> None:
    if token:
        await session.execute(
            delete(AdminSession).where(AdminSession.token_hash == hash_session_token(token))
        )
        await session.commit()


@dataclass(frozen=True)
class UserSessionContext:
    """Authenticated user and its session row / 已驗證的一般使用者與 Session。"""

    user: User
    session: UserSession


def _session_expiry() -> datetime:
    settings = get_settings()
    return datetime.now(UTC) + timedelta(hours=settings.user_session_hours)


async def create_user_session(
    session: AsyncSession,
    user: User,
    device_label: str,
) -> tuple[UserSession, str]:
    """Create a revocable user session and return its raw cookie token.

    建立可撤銷的一般使用者 Session，並回傳只會放進 Cookie 的明文 Token。
    """
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    user_session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        device_label=device_label[:160] or "瀏覽器",
        expires_at=_session_expiry(),
        last_seen_at=now,
    )
    session.add(user_session)
    await session.commit()
    await session.refresh(user_session)
    return user_session, token


def set_user_session_cookie(response: Response, token: str) -> None:
    """Set the browser-only user session cookie / 設定只供瀏覽器使用的使用者 Session Cookie。"""
    settings = get_settings()
    response.set_cookie(
        key=settings.user_session_cookie,
        value=token,
        max_age=settings.user_session_hours * 60 * 60,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


async def require_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    session_token: Annotated[str | None, Cookie(alias="bitemap_user_session")] = None,
) -> UserSessionContext:
    """Require a live user session and refresh last-seen metadata.

    預設拒絕未登入請求，並更新目前 Session 的最後活動時間。
    """
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user authentication required",
        )

    now = datetime.now(UTC)
    result = await session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(
            UserSession.token_hash == hash_session_token(session_token),
            UserSession.expires_at > now,
            User.is_active.is_(True),
            User.role == "user",
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user authentication required",
        )

    user_session, user = row
    user_session.last_seen_at = now
    await session.commit()
    return UserSessionContext(user=user, session=user_session)


async def revoke_user_session(session: AsyncSession, token: str | None) -> None:
    """Revoke one user session by its one-way token digest / 撤銷單一使用者 Session。"""
    if token:
        await session.execute(
            delete(UserSession).where(UserSession.token_hash == hash_session_token(token))
        )
        await session.commit()
