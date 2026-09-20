"""Administrator authentication and authorization / 管理員驗證與授權。"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.core.database import get_session
from api.domain.models import AdminSession, User

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password with Argon2id / 使用 Argon2id 雜湊密碼。"""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify without exposing hash failures / 驗證密碼且不洩漏雜湊錯誤。"""
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
