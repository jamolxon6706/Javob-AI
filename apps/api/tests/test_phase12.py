"""Phase 12 — Growth layer tests.

Tests cover:
- Contact CRUD + opt-in/opt-out
- Segment creation + preview
- Campaign lifecycle (create → schedule → cancel)
- Drip sequence CRUD + activate/deactivate
- Product catalog CRUD
- Opt-in link generation
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures (reuse pattern from existing tests)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Register a user and return bearer headers."""
    otp_resp = await client.post("/auth/request-otp", json={"phone": "+998901112233"})
    assert otp_resp.status_code == 200
    otp = otp_resp.json()["otp"]
    verify_resp = await client.post("/auth/verify", json={"phone": "+998901112233", "otp": otp})
    token = verify_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def tenant_headers(client: AsyncClient, auth_headers: dict) -> dict[str, str]:
    """Headers for an already-tenant-having user.

    BUG FIX: this used to additionally POST to /tenants to "create" a
    tenant, but no such endpoint exists (javobai/tenants/router.py only
    exposes GET/PATCH /tenants/me) — every signup via /auth/verify already
    auto-provisions a tenant (see every other passing test in this suite,
    e.g. test_tenant_isolation.py), so that extra call always 404'd and
    failed every single Phase 12 test before it even started.
    """
    return auth_headers


# ─────────────────────────────────────────────────────────────────────────────
# Contacts
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_contacts_empty(client: AsyncClient, tenant_headers: dict) -> None:
    resp = await client.get("/growth/contacts", headers=tenant_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_segment_create_and_preview(client: AsyncClient, tenant_headers: dict) -> None:
    # Create segment
    resp = await client.post(
        "/growth/segments",
        json={"name": "VIP", "filters": {"opt_in": True}},
        headers=tenant_headers,
    )
    assert resp.status_code == 201
    seg_id = resp.json()["id"]
    assert resp.json()["name"] == "VIP"

    # Preview (empty but should not error)
    preview = await client.post(f"/growth/segments/{seg_id}/preview", headers=tenant_headers)
    assert preview.status_code == 200
    assert "count" in preview.json()
    assert "sample" in preview.json()


@pytest.mark.anyio
async def test_segment_not_found(client: AsyncClient, tenant_headers: dict) -> None:
    resp = await client.get("/growth/segments/nonexistent-id", headers=tenant_headers)
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Campaigns
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_campaign_lifecycle(client: AsyncClient, tenant_headers: dict) -> None:
    # Create draft
    resp = await client.post(
        "/growth/campaigns",
        json={
            "name": "Yangi yil kampaniyasi",
            "campaign_type": "broadcast",
            "template": {"text": "Yangi yilingiz muborak!"},
        },
        headers=tenant_headers,
    )
    assert resp.status_code == 201
    camp = resp.json()
    assert camp["status"] == "draft"
    camp_id = camp["id"]

    # Get
    get_resp = await client.get(f"/growth/campaigns/{camp_id}", headers=tenant_headers)
    assert get_resp.status_code == 200

    # Update
    put_resp = await client.put(
        f"/growth/campaigns/{camp_id}",
        json={
            "name": "Yangi yil kampaniyasi (yangilangan)",
            "campaign_type": "broadcast",
            "template": {"text": "Yangilangan matn"},
        },
        headers=tenant_headers,
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["name"] == "Yangi yil kampaniyasi (yangilangan)"

    # Cancel
    cancel_resp = await client.post(f"/growth/campaigns/{camp_id}/cancel", headers=tenant_headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "failed"


@pytest.mark.anyio
async def test_campaign_delete(client: AsyncClient, tenant_headers: dict) -> None:
    resp = await client.post(
        "/growth/campaigns",
        json={"name": "O'chiriladigan", "campaign_type": "broadcast", "template": {}},
        headers=tenant_headers,
    )
    camp_id = resp.json()["id"]
    del_resp = await client.delete(f"/growth/campaigns/{camp_id}", headers=tenant_headers)
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/growth/campaigns/{camp_id}", headers=tenant_headers)
    assert get_resp.status_code == 404


@pytest.mark.anyio
async def test_send_now_requires_segment(client: AsyncClient, tenant_headers: dict) -> None:
    resp = await client.post(
        "/growth/campaigns",
        json={"name": "No segment", "campaign_type": "broadcast", "template": {"text": "hi"}},
        headers=tenant_headers,
    )
    camp_id = resp.json()["id"]
    send_resp = await client.post(f"/growth/campaigns/{camp_id}/send-now", headers=tenant_headers)
    assert send_resp.status_code == 400
    assert "segment" in send_resp.json()["detail"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Drip Sequences
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_drip_sequence_crud(client: AsyncClient, tenant_headers: dict) -> None:
    # Create with steps
    resp = await client.post(
        "/growth/drip-sequences",
        json={
            "name": "Xush kelibsiz seriyasi",
            "trigger_type": "first_contact",
            "trigger_config": {},
            "steps": [
                {"step_order": 1, "step_type": "message", "config": {"text": "Salom!"}},
                {"step_order": 2, "step_type": "wait", "config": {}, "wait_minutes": 1440},
                {"step_order": 3, "step_type": "message", "config": {"text": "Savol bormi?"}},
            ],
        },
        headers=tenant_headers,
    )
    assert resp.status_code == 201
    seq = resp.json()
    assert len(seq["steps"]) == 3
    assert seq["is_active"] is False
    seq_id = seq["id"]

    # Activate
    act_resp = await client.post(f"/growth/drip-sequences/{seq_id}/activate", headers=tenant_headers)
    assert act_resp.status_code == 200
    assert act_resp.json()["is_active"] is True

    # Deactivate
    deact_resp = await client.post(f"/growth/drip-sequences/{seq_id}/deactivate", headers=tenant_headers)
    assert deact_resp.status_code == 200
    assert deact_resp.json()["is_active"] is False

    # Delete
    del_resp = await client.delete(f"/growth/drip-sequences/{seq_id}", headers=tenant_headers)
    assert del_resp.status_code == 204


# ─────────────────────────────────────────────────────────────────────────────
# Products
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_product_crud(client: AsyncClient, tenant_headers: dict) -> None:
    # Create
    resp = await client.post(
        "/growth/products",
        json={
            "name": "Premium paket",
            "description": "Eng yaxshi xizmat",
            "price_uzs": 500000,
            "checkout_url": "https://example.uz/buy/premium",
            "in_stock": True,
        },
        headers=tenant_headers,
    )
    assert resp.status_code == 201
    prod = resp.json()
    assert prod["price_uzs"] == 500000
    assert prod["name"] == "Premium paket"
    prod_id = prod["id"]

    # List
    list_resp = await client.get("/growth/products", headers=tenant_headers)
    assert list_resp.status_code == 200
    assert any(p["id"] == prod_id for p in list_resp.json())

    # Update
    put_resp = await client.put(
        f"/growth/products/{prod_id}",
        json={"name": "Premium paket (yangi)", "price_uzs": 600000, "in_stock": True},
        headers=tenant_headers,
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["price_uzs"] == 600000

    # Soft delete
    del_resp = await client.delete(f"/growth/products/{prod_id}", headers=tenant_headers)
    assert del_resp.status_code == 204

    # Should not appear in list
    list_resp2 = await client.get("/growth/products", headers=tenant_headers)
    assert not any(p["id"] == prod_id for p in list_resp2.json())


# ─────────────────────────────────────────────────────────────────────────────
# Opt-in Links
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_opt_in_link_create_and_list(client: AsyncClient, tenant_headers: dict) -> None:
    resp = await client.post(
        "/growth/opt-in-links",
        json={"name": "Instagram QR", "platform": "instagram"},
        headers=tenant_headers,
    )
    assert resp.status_code == 201
    link = resp.json()
    assert len(link["slug"]) == 8
    assert link["platform"] == "instagram"
    link_id = link["id"]

    list_resp = await client.get("/growth/opt-in-links", headers=tenant_headers)
    assert any(l["id"] == link_id for l in list_resp.json())

    del_resp = await client.delete(f"/growth/opt-in-links/{link_id}", headers=tenant_headers)
    assert del_resp.status_code == 204


@pytest.mark.anyio
async def test_public_opt_in_redirect(client: AsyncClient, tenant_headers: dict) -> None:
    # Create a link
    create_resp = await client.post(
        "/growth/opt-in-links",
        json={"name": "Test link", "platform": "telegram", "welcome_message": "Xush kelibsiz!"},
        headers=tenant_headers,
    )
    slug = create_resp.json()["slug"]

    # Hit public endpoint (no auth)
    pub_resp = await client.get(f"/opt-in/{slug}")
    assert pub_resp.status_code == 200
    data = pub_resp.json()
    assert data["slug"] == slug
    assert data["welcome_message"] == "Xush kelibsiz!"
    assert data["scan_count"] == 1


@pytest.mark.anyio
async def test_tenant_isolation_campaigns(client: AsyncClient) -> None:
    """Tenant A cannot see Tenant B's campaigns."""
    # Register user A
    await client.post("/auth/request-otp", json={"phone": "+998900001111"})
    otp_a = (await client.post("/auth/request-otp", json={"phone": "+998900001111"})).json()["otp"]
    token_a = (await client.post("/auth/verify", json={"phone": "+998900001111", "otp": otp_a})).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    await client.post("/tenants", json={"name": "Tenant A"}, headers=headers_a)
    camp_resp = await client.post(
        "/growth/campaigns",
        json={"name": "A ning kampaniyasi", "campaign_type": "broadcast", "template": {}},
        headers=headers_a,
    )
    camp_id = camp_resp.json()["id"]

    # Register user B
    otp_b = (await client.post("/auth/request-otp", json={"phone": "+998900002222"})).json()["otp"]
    token_b = (await client.post("/auth/verify", json={"phone": "+998900002222", "otp": otp_b})).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    await client.post("/tenants", json={"name": "Tenant B"}, headers=headers_b)

    # B cannot access A's campaign
    resp = await client.get(f"/growth/campaigns/{camp_id}", headers=headers_b)
    assert resp.status_code == 404
