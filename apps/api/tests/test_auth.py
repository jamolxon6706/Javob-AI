"""Auth flow: request OTP → verify → get me → refresh token."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_auth_flow(client: AsyncClient) -> None:
    phone = "+998901234567"

    # 1. Request OTP
    r = await client.post("/auth/request-otp", json={"phone": phone})
    assert r.status_code == 200
    data = r.json()
    assert data["detail"] == "OTP sent"
    otp = data["otp"]  # dev-mode: OTP is returned in response
    assert otp and len(otp) == 6

    # 2. Verify OTP → get tokens
    r = await client.post("/auth/verify", json={"phone": phone, "otp": otp})
    assert r.status_code == 200
    tokens = r.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # 3. GET /auth/me
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    me = r.json()
    assert me["phone"] == phone
    assert me["role"] == "owner"
    assert me["tenant_id"]

    # 4. Refresh token (small sleep ensures iat differs → different JWT)
    import asyncio
    await asyncio.sleep(1)
    r = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    new_tokens = r.json()
    assert new_tokens["access_token"] != access  # new token issued

    # 5. Old refresh token is revoked
    r = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_otp_rejected(client: AsyncClient) -> None:
    phone = "+998909999999"
    await client.post("/auth/request-otp", json={"phone": phone})
    r = await client.post("/auth/verify", json={"phone": phone, "otp": "000000"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/auth/me")
    assert r.status_code in (401, 403)  # HTTPBearer: 403 without header, 401 with bad token
