"""
Cross-tenant isolation: user A cannot read or modify tenant B's FAQs.
"""
import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, phone: str) -> str:
    """Register a user and return their access token."""
    r = await client.post("/auth/request-otp", json={"phone": phone})
    otp = r.json()["otp"]
    r = await client.post("/auth/verify", json={"phone": phone, "otp": otp})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_faq_tenant_isolation(client: AsyncClient) -> None:
    token_a = await _register(client, "+998901111111")
    token_b = await _register(client, "+998902222222")

    # Tenant A creates a FAQ
    r = await client.post(
        "/faqs",
        json={"question": "Yetkazib berish qancha?", "answer": "Bepul"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 201
    faq_id = r.json()["id"]

    # Tenant B tries to read tenant A's FAQ — must get 404 (not 403, to avoid leaking existence)
    r = await client.get(
        f"/faqs/{faq_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404

    # Tenant B's FAQ list must be empty
    r = await client.get("/faqs", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 200
    assert r.json() == []

    # Tenant A can still read their own FAQ
    r = await client.get(f"/faqs/{faq_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200
    assert r.json()["question"] == "Yetkazib berish qancha?"
