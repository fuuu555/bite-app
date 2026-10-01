"""General-user profile services / 一般使用者個人資料服務。"""

from __future__ import annotations

import hashlib
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.domain.models import AvatarAsset, ProfileTag, User, UserProfile, UserSession
from api.domain.schemas import (
    AvatarAssetResponse,
    MyProfileResponse,
    ProfileTagResponse,
    PublicProfileResponse,
    UserProfileUpdate,
    UserSessionResponse,
)


def _tag_slug(display_name: str) -> str:
    """Build a stable readable slug, including for Traditional Chinese tags.

    建立穩定且可讀的 Tag slug，中文標籤也保留可辨識內容。
    """
    normalized = display_name.strip().casefold()
    slug = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "-", normalized).strip("-")
    if slug:
        return slug[:120]
    return f"tag-{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]}"


async def get_profile(session: AsyncSession, user_id: uuid.UUID) -> UserProfile | None:
    result = await session.execute(
        select(UserProfile)
        .options(selectinload(UserProfile.tags), selectinload(UserProfile.avatar_asset))
        .execution_options(populate_existing=True)
        .where(UserProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()


def avatar_url_for_profile(profile: UserProfile) -> str | None:
    """Resolve a local asset before falling back to an external URL.

    內建頭貼優先使用本地資產，沒有資產時才回退到既有外部 URL。
    """
    if profile.avatar_asset is not None:
        return f"/media/{profile.avatar_asset.storage_key}"
    return profile.avatar_url


def avatar_asset_response(asset: AvatarAsset) -> AvatarAssetResponse:
    return AvatarAssetResponse(
        id=asset.id,
        display_name=asset.display_name,
        url=f"/media/{asset.storage_key}",
        mime_type=asset.mime_type,
        file_size=asset.file_size,
        is_active=asset.is_active,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


async def list_active_avatar_assets(session: AsyncSession) -> list[AvatarAsset]:
    result = await session.execute(
        select(AvatarAsset)
        .where(AvatarAsset.is_active.is_(True))
        .order_by(AvatarAsset.display_name, AvatarAsset.created_at)
    )
    return list(result.scalars())


async def create_profile(
    session: AsyncSession,
    user: User,
    display_name: str,
    bio: str | None = None,
    avatar_url: str | None = None,
    tags: list[str] | None = None,
) -> UserProfile:
    resolved_tags = await resolve_tags(session, user.id, tags or [])
    profile = UserProfile(
        user_id=user.id,
        display_name=display_name,
        bio=bio,
        avatar_url=avatar_url,
        avatar_source="google" if avatar_url else "url",
        tags=resolved_tags,
    )
    session.add(profile)
    await session.flush()
    return profile


async def resolve_tags(
    session: AsyncSession,
    user_id: uuid.UUID,
    display_names: list[str],
) -> list[ProfileTag]:
    """Resolve system tags or create user tags without duplicating business facts.

    優先重用既有系統 Tag，找不到時才建立使用者建立的 Tag。
    """
    unique_names: list[str] = []
    seen: set[str] = set()
    for display_name in display_names:
        normalized = re.sub(r"\s+", " ", display_name).strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            unique_names.append(normalized)

    tags: list[ProfileTag] = []
    for display_name in unique_names:
        slug = _tag_slug(display_name)
        tag = (
            await session.execute(select(ProfileTag).where(ProfileTag.slug == slug))
        ).scalar_one_or_none()
        if tag is None:
            tag = ProfileTag(
                slug=slug,
                display_name=display_name,
                is_system=False,
                created_by_user_id=user_id,
            )
            session.add(tag)
            await session.flush()
        tags.append(tag)
    return tags


async def update_profile(
    session: AsyncSession,
    user: User,
    payload: UserProfileUpdate,
) -> UserProfile:
    profile = await get_profile(session, user.id)
    if profile is None:
        profile = await create_profile(session, user, payload.display_name or "BiteMap 使用者")

    values = payload.model_dump(exclude_unset=True, exclude={"tags", "avatar_asset_id"})
    for field, value in values.items():
        setattr(profile, field, value)
    if "avatar_url" in payload.model_fields_set:
        profile.avatar_source = "url"
        profile.avatar_asset_id = None
    if "avatar_asset_id" in payload.model_fields_set:
        if payload.avatar_asset_id is None:
            profile.avatar_asset_id = None
        else:
            asset = await session.scalar(
                select(AvatarAsset).where(
                    AvatarAsset.id == payload.avatar_asset_id,
                    AvatarAsset.is_active.is_(True),
                )
            )
            if asset is None:
                raise ValueError("avatar asset is not available")
            profile.avatar_source = "builtin"
            profile.avatar_asset_id = asset.id
    if "tags" in payload.model_fields_set and payload.tags is not None:
        profile.tags = await resolve_tags(session, user.id, payload.tags)
    await session.commit()
    refreshed = await get_profile(session, user.id)
    assert refreshed is not None
    return refreshed


def public_profile_response(user: User, profile: UserProfile) -> PublicProfileResponse:
    return PublicProfileResponse(
        id=user.id,
        display_name=profile.display_name,
        bio=profile.bio,
        avatar_url=avatar_url_for_profile(profile),
        avatar_source=profile.avatar_source,  # type: ignore[arg-type]
        avatar_asset_id=profile.avatar_asset_id,
        tags=[ProfileTagResponse.model_validate(tag) for tag in profile.tags],
    )


def my_profile_response(user: User, profile: UserProfile) -> MyProfileResponse:
    return MyProfileResponse(
        id=user.id,
        email=user.email,
        display_name=profile.display_name,
        bio=profile.bio,
        avatar_url=avatar_url_for_profile(profile),
        avatar_source=profile.avatar_source,  # type: ignore[arg-type]
        avatar_asset_id=profile.avatar_asset_id,
        tags=[ProfileTagResponse.model_validate(tag) for tag in profile.tags],
    )


def user_session_response(
    user_session: UserSession,
    current_session_id: uuid.UUID,
) -> UserSessionResponse:
    return UserSessionResponse(
        id=user_session.id,
        device_label=user_session.device_label,
        expires_at=user_session.expires_at,
        last_seen_at=user_session.last_seen_at,
        created_at=user_session.created_at,
        current=user_session.id == current_session_id,
    )
