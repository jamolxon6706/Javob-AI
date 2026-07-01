"""Tests for AI settings CRUD (Phase 7)."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_ai_settings_defaults(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/ai-settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm_enabled"] is True
    assert data["confidence_threshold"] == pytest.approx(0.65, abs=0.01)
    assert data["language_mode"] == "auto"
    assert isinstance(data["banned_topics"], list)


@pytest.mark.asyncio
async def test_update_ai_settings(auth_client: AsyncClient) -> None:
    patch_resp = await auth_client.patch(
        "/ai-settings",
        json={
            "brand_voice": "Samimiy va professional.",
            "confidence_threshold": 0.75,
            "llm_enabled": False,
            "banned_topics": ["siyosat", "raqobatchilar"],
            "language_mode": "uz",
        },
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["brand_voice"] == "Samimiy va professional."
    assert data["confidence_threshold"] == pytest.approx(0.75)
    assert data["llm_enabled"] is False
    assert "siyosat" in data["banned_topics"]
    assert data["language_mode"] == "uz"

    # persisted
    get_resp = await auth_client.get("/ai-settings")
    assert get_resp.json()["language_mode"] == "uz"


@pytest.mark.asyncio
async def test_ai_settings_tenant_isolation(
    auth_client: AsyncClient, second_auth_client: AsyncClient
) -> None:
    await auth_client.patch(
        "/ai-settings", json={"brand_voice": "Tenant A voice"}
    )
    resp = await second_auth_client.get("/ai-settings")
    assert resp.json().get("brand_voice") != "Tenant A voice"
