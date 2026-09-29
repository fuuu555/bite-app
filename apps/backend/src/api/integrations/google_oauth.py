"""Google OpenID Connect helpers / Google OpenID Connect 整合工具。"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from api.core.config import get_settings


class GoogleOAuthNotConfigured(RuntimeError):
    """Raised when deployment has not provided Google OAuth credentials.

    部署環境缺少 Google OAuth 憑證時使用，避免以不完整設定啟動登入流程。
    """


class GoogleOAuthError(RuntimeError):
    """Raised when Google does not return a usable identity.

    Google 回應無法建立可信任身分時使用，不把供應商細節洩漏至外部。
    """


@dataclass(frozen=True)
class GoogleIdentity:
    provider_subject: str
    email: str
    email_verified: bool
    display_name: str
    avatar_url: str | None


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def create_authorization_request() -> tuple[str, str, str]:
    """Create an OIDC authorization URL with state and PKCE protection.

    建立具備 state 與 PKCE 保護的 OIDC 授權網址。
    """
    settings = get_settings()
    if not settings.google_oauth_configured:
        raise GoogleOAuthNotConfigured
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = _base64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    query = urlencode(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{settings.google_oauth_authorization_endpoint}?{query}", state, code_verifier


async def exchange_google_code(code: str, code_verifier: str) -> GoogleIdentity:
    """Exchange the one-time code and return only normalized identity fields.

    交換一次性授權碼，只回傳正規化身分欄位，不保存 Google Token。
    """
    settings = get_settings()
    if not settings.google_oauth_configured:
        raise GoogleOAuthNotConfigured

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                settings.google_oauth_token_endpoint,
                data={
                    "code": code,
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret,
                    "redirect_uri": settings.google_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
            )
            if token_response.is_error:
                raise GoogleOAuthError("token exchange failed")
            token_payload = token_response.json()
            access_token = token_payload.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise GoogleOAuthError("missing access token")

            userinfo_response = await client.get(
                settings.google_oauth_userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_response.is_error:
                raise GoogleOAuthError("userinfo request failed")
            payload = userinfo_response.json()
    except (httpx.HTTPError, ValueError) as caught:
        raise GoogleOAuthError("Google request failed") from caught

    subject = payload.get("sub")
    email = payload.get("email")
    email_verified = payload.get("email_verified") is True
    if not isinstance(subject, str) or not subject:
        raise GoogleOAuthError("missing subject")
    if not isinstance(email, str) or not email or not email_verified:
        raise GoogleOAuthError("verified email required")
    display_name = payload.get("name") or email.split("@", 1)[0]
    if not isinstance(display_name, str):
        display_name = email.split("@", 1)[0]
    avatar_url = payload.get("picture")
    if not isinstance(avatar_url, str) or not avatar_url.startswith("https://"):
        avatar_url = None
    else:
        avatar_url = avatar_url[:1000]
    return GoogleIdentity(
        provider_subject=subject,
        email=email.strip().lower(),
        email_verified=True,
        display_name=display_name.strip()[:80] or "BiteMap 使用者",
        avatar_url=avatar_url,
    )
