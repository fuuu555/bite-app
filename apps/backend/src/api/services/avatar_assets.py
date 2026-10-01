"""Local avatar asset storage / 本地頭貼資產儲存。"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.domain.models import AvatarAsset, User

MEDIA_ROOT = Path(__file__).resolve().parents[3] / "media"
AVATAR_ROOT = MEDIA_ROOT / "avatars"
MAX_AVATAR_BYTES = 5 * 1024 * 1024

_IMAGE_SIGNATURES: tuple[tuple[str, str, bytes], ...] = (
    ("image/jpeg", ".jpg", b"\xff\xd8\xff"),
    ("image/png", ".png", b"\x89PNG\r\n\x1a\n"),
    ("image/webp", ".webp", b"RIFF"),
)


def _detect_image_type(data: bytes) -> tuple[str, str] | None:
    """Allow only known image signatures / 只允許明確的圖片檔案簽章。"""
    for mime_type, extension, signature in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            if mime_type == "image/webp" and data[8:12] != b"WEBP":
                continue
            return mime_type, extension
    return None


async def create_avatar_asset(
    session: AsyncSession,
    admin: User,
    upload: UploadFile,
    display_name: str,
) -> AvatarAsset:
    """Validate and persist one admin-uploaded local avatar.

    驗證並保存一個由管理員上傳的本地頭貼；檔名永遠由伺服器產生。
    """
    normalized_name = " ".join(display_name.split())
    if not normalized_name or len(normalized_name) > 80:
        raise ValueError("avatar display name must be between 1 and 80 characters")

    data = await upload.read(MAX_AVATAR_BYTES + 1)
    if len(data) > MAX_AVATAR_BYTES:
        raise ValueError("avatar file is too large")
    detected = _detect_image_type(data)
    if detected is None:
        raise ValueError("only JPEG, PNG, or WebP images are allowed")
    mime_type, extension = detected
    if upload.content_type and upload.content_type != mime_type:
        raise ValueError("image content type does not match its file signature")

    asset_id = uuid.uuid4()
    storage_key = f"avatars/{asset_id}{extension}"
    target = AVATAR_ROOT / f"{asset_id}{extension}"
    await asyncio.to_thread(AVATAR_ROOT.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(target.write_bytes, data)
    asset = AvatarAsset(
        id=asset_id,
        display_name=normalized_name,
        storage_key=storage_key,
        mime_type=mime_type,
        file_size=len(data),
        is_active=True,
        created_by_user_id=admin.id,
    )
    session.add(asset)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await asyncio.to_thread(target.unlink, missing_ok=True)
        raise
    await session.refresh(asset)
    return asset


def avatar_file_for_asset(asset: AvatarAsset) -> Path:
    """Resolve only a server-generated avatar key / 僅解析伺服器產生的頭貼 key。"""
    filename = Path(asset.storage_key).name
    target = AVATAR_ROOT / filename
    if target.parent != AVATAR_ROOT:
        raise ValueError("invalid avatar storage key")
    return target
