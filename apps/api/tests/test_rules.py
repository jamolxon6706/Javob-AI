"""Tests for the rules CRUD API (Phase 7)."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_rule(auth_client: AsyncClient) -> None:
    payload = {
        "name": "Salom so'zi",
        "trigger_type": "keyword",
        "trigger_value": {"keywords": ["salom", "hi"]},
        "action_type": "reply",
        "action_value": {"text": "Xush kelibsiz!"},
        "priority": 10,
    }
    create_resp = await auth_client.post("/rules", json=payload)
    assert create_resp.status_code == 201
    rule = create_resp.json()
    assert rule["name"] == "Salom so'zi"
    assert rule["trigger_type"] == "keyword"
    assert rule["is_active"] is True

    list_resp = await auth_client.get("/rules")
    assert list_resp.status_code == 200
    ids = [r["id"] for r in list_resp.json()]
    assert rule["id"] in ids


@pytest.mark.asyncio
async def test_update_rule(auth_client: AsyncClient) -> None:
    create_resp = await auth_client.post(
        "/rules",
        json={
            "name": "Test rule",
            "trigger_type": "keyword",
            "trigger_value": {},
            "action_type": "handoff",
            "action_value": {},
        },
    )
    rule_id = create_resp.json()["id"]

    patch_resp = await auth_client.patch(
        f"/rules/{rule_id}", json={"name": "Updated rule", "is_active": False}
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["name"] == "Updated rule"
    assert updated["is_active"] is False


@pytest.mark.asyncio
async def test_delete_rule(auth_client: AsyncClient) -> None:
    create_resp = await auth_client.post(
        "/rules",
        json={
            "name": "To delete",
            "trigger_type": "stop_word",
            "trigger_value": {},
            "action_type": "silence",
            "action_value": {},
        },
    )
    rule_id = create_resp.json()["id"]

    del_resp = await auth_client.delete(f"/rules/{rule_id}")
    assert del_resp.status_code == 204

    list_resp = await auth_client.get("/rules")
    ids = [r["id"] for r in list_resp.json()]
    assert rule_id not in ids


@pytest.mark.asyncio
async def test_rule_tenant_isolation(
    auth_client: AsyncClient, second_auth_client: AsyncClient
) -> None:
    """Tenant A's rule must not be visible to Tenant B."""
    create_resp = await auth_client.post(
        "/rules",
        json={
            "name": "Tenant A rule",
            "trigger_type": "first_contact",
            "trigger_value": {},
            "action_type": "reply",
            "action_value": {"text": "hello"},
        },
    )
    rule_id = create_resp.json()["id"]

    list_resp = await second_auth_client.get("/rules")
    ids = [r["id"] for r in list_resp.json()]
    assert rule_id not in ids

    patch_resp = await second_auth_client.patch(
        f"/rules/{rule_id}", json={"name": "Hacked"}
    )
    assert patch_resp.status_code == 404
