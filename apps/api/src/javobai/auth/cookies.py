"""
Phase 6 — HttpOnly cookie auth transport.

The dashboard (apps/web) reads the access/refresh JWTs from HttpOnly cookies and
forwards them as `Authorization: Bearer` to FastAPI. The FastAPI side still uses
the existing `HTTPBearer` dependency — we don't add a second auth code path. The
only thing this module does is set/clear the cookies on `/auth/verify`,
`/auth/refresh`, and `/auth/logout` responses so the browser stores them.

Cookie attributes (all configurable via env, see `Settings` in `javobai.config`):
  HttpOnly  — JS cannot read (XSS-safe).
  Secure    — only sent over HTTPS (toggleable for local HTTP dev).
  SameSite  — Lax by default; works for same-origin + top-level navigations.
  Path=/    — sent on every API call.
  Domain    — empty in dev; set to ".javobai.uz" in prod so the cookie crosses
              subdomains (app. ↔ api.) if the BFF lives on a different host.
"""
from __future__ import annotations

from fastapi import Response

from javobai.config import Settings

ACCESS_COOKIE = "javobai_access"
REFRESH_COOKIE = "javobai_refresh"


def _common_attrs(settings: Settings) -> dict[str, object]:
    """Cookie attrs shared between set and clear."""
    attrs: dict[str, object] = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }
    if settings.cookie_domain:
        attrs["domain"] = settings.cookie_domain
    return attrs


def set_auth_cookies(
    response: Response,
    *,
    access: str,
    refresh: str,
    settings: Settings,
) -> None:
    """Attach HttpOnly access + refresh cookies to a FastAPI Response."""
    attrs = _common_attrs(settings)
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=settings.jwt_access_expire_minutes * 60,
        **attrs,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=settings.jwt_refresh_expire_days * 86400,
        **attrs,
    )


def clear_auth_cookies(response: Response, *, settings: Settings) -> None:
    """Tell the browser to drop both cookies immediately."""
    # delete_cookie wants the same attrs the cookie was set with (esp. path/domain).
    attrs = _common_attrs(settings)
    response.delete_cookie(ACCESS_COOKIE, **{k: v for k, v in attrs.items() if k != "httponly"})
    response.delete_cookie(REFRESH_COOKIE, **{k: v for k, v in attrs.items() if k != "httponly"})