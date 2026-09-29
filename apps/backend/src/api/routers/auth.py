"""General-user authentication and profile endpoints / 一般使用者驗證與個人頁 API。"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.responses import RedirectResponse

from api.core.config import get_settings
from api.core.database import get_session
from api.core.security import (
    UserSessionContext,
    create_user_session,
    require_user,
    revoke_user_session,
    set_user_session_cookie,
)
from api.domain.models import User, UserIdentity, UserProfile, UserSession
from api.domain.schemas import (
    MyProfileResponse,
    PublicProfileResponse,
    UserProfileUpdate,
    UserResponse,
    UserSessionResponse,
)
from api.integrations.google_oauth import (
    GoogleOAuthError,
    GoogleOAuthNotConfigured,
    create_authorization_request,
    exchange_google_code,
)
from api.services.profile import (
    create_profile,
    get_profile,
    my_profile_response,
    public_profile_response,
    update_profile,
    user_session_response,
)

router = APIRouter(prefix="/api/v1", tags=["auth"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UserSessionContext, Depends(require_user)]
SessionCookie = Annotated[str | None, Cookie(alias="bitemap_user_session")]


def _device_label(request: Request) -> str:
    """Keep a short, non-sensitive browser label for device management UI."""
    return request.headers.get("user-agent", "瀏覽器")[:160] or "瀏覽器"


async def _get_or_create_profile(session: AsyncSession, user: User) -> UserProfile:
    profile = await get_profile(session, user.id)
    if profile is not None:
        return profile
    profile = await create_profile(session, user, display_name=user.email.split("@", 1)[0][:80])
    await session.commit()
    refreshed = await get_profile(session, user.id)
    assert refreshed is not None
    return refreshed


def _clear_google_cookies(response: Response) -> None:
    response.delete_cookie("bitemap_google_state", path="/api/v1/auth/google")
    response.delete_cookie("bitemap_google_verifier", path="/api/v1/auth/google")


@router.get("/auth/google/start")
async def google_start() -> RedirectResponse:
    """Start Google OIDC Authorization Code + PKCE flow / 開始 Google OIDC 登入。"""
    try:
        authorization_url, state, verifier = create_authorization_request()
    except GoogleOAuthNotConfigured as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google login is not configured",
        ) from error

    settings = get_settings()
    response = RedirectResponse(authorization_url, status_code=status.HTTP_303_SEE_OTHER)
    for name, value in (("bitemap_google_state", state), ("bitemap_google_verifier", verifier)):
        response.set_cookie(
            key=name,
            value=value,
            max_age=600,
            httponly=True,
            secure=settings.secure_cookies,
            samesite="lax",
            path="/api/v1/auth/google",
        )
    return response


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    session: SessionDep,
    state_cookie: Annotated[str | None, Cookie(alias="bitemap_google_state")] = None,
    verifier_cookie: Annotated[str | None, Cookie(alias="bitemap_google_verifier")] = None,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Finish Google login without persisting provider tokens / 完成 Google 登入。"""
    settings = get_settings()
    login_url = f"{settings.frontend_url.rstrip('/')}/login"
    if error:
        response = RedirectResponse(f"{login_url}?error=google_login_failed", status_code=303)
        _clear_google_cookies(response)
        return response
    if (
        not code
        or not state
        or not state_cookie
        or not verifier_cookie
        or not secrets.compare_digest(state, state_cookie)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid OAuth state")

    try:
        identity = await exchange_google_code(code, verifier_cookie)
    except (GoogleOAuthError, GoogleOAuthNotConfigured) as caught:
        response = RedirectResponse(f"{login_url}?error=google_login_failed", status_code=303)
        _clear_google_cookies(response)
        if isinstance(caught, GoogleOAuthNotConfigured):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google login is not configured",
            ) from caught
        return response

    identity_result = await session.execute(
        select(UserIdentity).where(
            UserIdentity.provider == "google",
            UserIdentity.provider_subject == identity.provider_subject,
        )
    )
    linked_identity = identity_result.scalar_one_or_none()
    if linked_identity is not None:
        user_result = await session.execute(
            select(User).where(User.id == linked_identity.user_id, User.role == "user")
        )
        user = user_result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user unavailable")
    else:
        existing_email = await session.execute(
            select(User).where(User.email == identity.email, User.role == "user")
        )
        if existing_email.scalar_one_or_none() is not None:
            response = RedirectResponse(f"{login_url}?error=account_conflict", status_code=303)
            _clear_google_cookies(response)
            return response
        user = User(
            email=identity.email,
            password_hash=None,
            role="user",
            is_active=True,
        )
        session.add(user)
        try:
            await session.flush()
            session.add(
                UserIdentity(
                    user_id=user.id,
                    provider="google",
                    provider_subject=identity.provider_subject,
                )
            )
            await create_profile(
                session,
                user,
                display_name=identity.display_name,
                avatar_url=identity.avatar_url,
            )
            await session.commit()
        except IntegrityError as caught:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="account conflict"
            ) from caught

    _, token = await create_user_session(session, user, _device_label(request))
    response = RedirectResponse(f"{settings.frontend_url.rstrip('/')}/profile", status_code=303)
    set_user_session_cookie(response, token)
    _clear_google_cookies(response)
    return response


@router.post("/auth/session/refresh", response_model=UserResponse)
async def refresh_session(
    response: Response,
    session: SessionDep,
    current: UserDep,
    session_token: SessionCookie = None,
) -> UserResponse:
    """Extend only a live session / 只延長仍有效的 Session。"""
    current.session.expires_at = datetime.now(UTC) + timedelta(
        hours=get_settings().user_session_hours
    )
    await session.commit()
    # Setting the existing HttpOnly cookie again refreshes only its max-age.
    # 明文 Token 仍只存在既有 HttpOnly Cookie，重新設定只更新瀏覽器保存期限。
    if session_token:
        set_user_session_cookie(response, session_token)
    return UserResponse(id=current.user.id, email=current.user.email, role="user")


@router.delete("/auth/session", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDep,
    session_token: SessionCookie = None,
) -> None:
    await revoke_user_session(session, session_token)
    response.delete_cookie(get_settings().user_session_cookie, path="/")


@router.get("/auth/me", response_model=UserResponse)
async def current_user(current: UserDep) -> UserResponse:
    return UserResponse(id=current.user.id, email=current.user.email, role="user")


@router.get("/me/profile", response_model=MyProfileResponse)
async def read_my_profile(current: UserDep, session: SessionDep) -> MyProfileResponse:
    profile = await _get_or_create_profile(session, current.user)
    return my_profile_response(current.user, profile)


@router.patch("/me/profile", response_model=MyProfileResponse)
async def patch_my_profile(
    payload: UserProfileUpdate,
    current: UserDep,
    session: SessionDep,
) -> MyProfileResponse:
    profile = await update_profile(session, current.user, payload)
    return my_profile_response(current.user, profile)


@router.get("/profiles/{user_id}", response_model=PublicProfileResponse)
async def read_public_profile(user_id: uuid.UUID, session: SessionDep) -> PublicProfileResponse:
    result = await session.execute(
        select(User).where(
            User.id == user_id,
            User.role == "user",
            User.is_active.is_(True),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    profile = await session.execute(
        select(UserProfile)
        .options(selectinload(UserProfile.tags))
        .where(UserProfile.user_id == user_id)
    )
    user_profile = profile.scalar_one_or_none()
    if user_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return public_profile_response(user, user_profile)


@router.get("/me/sessions", response_model=list[UserSessionResponse])
async def list_my_sessions(current: UserDep, session: SessionDep) -> list[UserSessionResponse]:
    result = await session.execute(
        select(UserSession)
        .where(UserSession.user_id == current.user.id)
        .order_by(UserSession.last_seen_at.desc())
    )
    return [user_session_response(item, current.session.id) for item in result.scalars()]


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_my_session(
    session_id: uuid.UUID,
    current: UserDep,
    session: SessionDep,
) -> None:
    result = await session.execute(
        delete(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == current.user.id,
        )
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    await session.commit()
