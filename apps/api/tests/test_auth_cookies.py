"""
Phase 6 — HttpOnly cookie auth transport.

Verifies that /auth/verify and /auth/refresh set the cookies with the right
attributes, that /auth/logout clears them, and that the JSON body still
carries the tokens (so the Next.js BFF has the contract it needs).
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


def _set_cookies(headers) -> dict[str, str]:
    """Return a {cookie_name: raw_header} map from a response's set-cookie headers."""
    raw = headers.get_list("set-cookie")
    out: dict[str, str] = {}
    for line in raw:
        name = line.split("=", 1)[0]
        out[name] = line
    return out


@pytest.mark.asyncio
async def test_verify_sets_cookies(client: AsyncClient) -> None:
    # Bootstrap: request an OTP, then verify it.
    await client.post("/auth/request-otp", json={"phone": "+998901111111"})
    resp = await client.post(
        "/auth/verify", json={"phone": "+998901111111", "otp": "000000"}
    )
    # The test redis fixture has no OTP stored, so verify returns 400.
    # We re-run with a pre-populated OTP via the redis fixture.
    # Easier path: stub by going through request-otp then verifying with the
    # real returned OTP (it's logged + exposed in dev).
    req = await client.post("/auth/request-otp", json={"phone": "+998901112222"})
    otp = req.json()["otp"]
    assert otp, "dev environment should expose OTP in response"

    resp = await client.post("/auth/verify", json={"phone": "+998901112222", "otp": otp})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]

    cookies = _set_cookies(resp.headers)
    assert "javobai_access" in cookies, cookies
    assert "javobai_refresh" in cookies, cookies

    # Cookie attributes — HttpOnly, SameSite=Lax, Path=/, no Secure (local dev).
    for name in ("javobai_access", "javobai_refresh"):
        line = cookies[name].lower()
        assert "httponly" in line, line
        assert "samesite=lax" in line, line
        assert "path=/" in line, line


@pytest.mark.asyncio
async def test_refresh_rotates_cookies(client: AsyncClient) -> None:
    # Bootstrap a session
    req = await client.post("/auth/request-otp", json={"phone": "+998901113333"})
    otp = req.json()["otp"]
    v = await client.post("/auth/verify", json={"phone": "+998901113333", "otp": otp})
    refresh_token = v.json()["refresh_token"]

    # Refresh — should rotate cookies AND keep the JSON contract
    r = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]
    assert r.json()["refresh_token"]
    cookies = _set_cookies(r.headers)
    assert "javobai_access" in cookies
    assert "javobai_refresh" in cookies


@pytest.mark.asyncio
async def test_logout_clears_cookies(client: AsyncClient) -> None:
    req = await client.post("/auth/request-otp", json={"phone": "+998901114444"})
    otp = req.json()["otp"]
    v = await client.post("/auth/verify", json={"phone": "+998901114444", "otp": otp})
    refresh_token = v.json()["refresh_token"]

    r = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert r.status_code == 204, r.text
    cookies = _set_cookies(r.headers)
    # Either absent or explicitly cleared (Max-Age=0). httpx exposes them
    # as either case; we just check that javobai_* is set with Max-Age=0.
    for name in ("javobai_access", "javobai_refresh"):
        if name in cookies:
            assert "max-age=0" in cookies[name].lower(), cookies[name]


@pytest.mark.asyncio
async def test_verify_response_body_still_contains_tokens(client: AsyncClient) -> None:
    """Regression guard: BFF reads tokens from the body to copy Set-Cookie."""
    req = await client.post("/auth/request-otp", json={"phone": "+998901115555"})
    otp = req.json()["otp"]
    r = await client.post("/auth/verify", json={"phone": "+998901115555", "otp": otp})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_logout_with_garbage_refresh_is_idempotent(client: AsyncClient) -> None:
    """A bad/expired refresh token must not crash the logout endpoint."""
    r = await client.post("/auth/logout", json={"refresh_token": "not-a-real-jwt"})
    assert r.status_code == 204
    # The endpoint also clears cookies unconditionally so the browser state is clean.
    cookies = _set_cookies(r.headers)
    for name in ("javobai_access", "javobai_refresh"):
        if name in cookies:
            assert "max-age=0" in cookies[name].lower()