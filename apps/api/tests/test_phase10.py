"""
Faza 10 tests: Meta normalizer, IG comment dedup, FB window check.
Run: pytest apps/api/tests/test_phase10.py -v
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from worker.adapters.meta.normalizer import parse_meta_webhook
from worker.adapters.meta.instagram_dispatcher import InstagramDispatcher
from worker.adapters.meta.facebook_dispatcher import FacebookDispatcher
from worker.adapters.meta.client import MetaGraphClient, MetaAPIError


# ── Fixtures ────────────────────────────────────────────────────────────────

TENANT_ID = str(uuid4())
CHANNEL_ID = str(uuid4())
PAGE_ID = "111222333"
USER_ID = "999888777"
COMMENT_ID = "cmt_abc123"


def make_ig_dm_payload() -> dict:
    return {
        "object": "instagram",
        "entry": [
            {
                "id": PAGE_ID,
                "messaging": [
                    {
                        "sender": {"id": USER_ID},
                        "recipient": {"id": PAGE_ID},
                        "timestamp": 1700000000000,
                        "message": {
                            "mid": "mid.abc123",
                            "text": "Salom, mahsulot bormi?",
                        },
                    }
                ],
            }
        ],
    }


def make_ig_comment_payload() -> dict:
    return {
        "object": "instagram",
        "entry": [
            {
                "id": PAGE_ID,
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "item": "comment",
                            "verb": "add",
                            "comment_id": COMMENT_ID,
                            "post_id": "post_xyz",
                            "from": {"id": USER_ID, "name": "Sardor"},
                            "message": "Narxi qancha?",
                            "created_time": 1700000000,
                        },
                    }
                ],
            }
        ],
    }


def make_fb_dm_payload() -> dict:
    return {
        "object": "page",
        "entry": [
            {
                "id": PAGE_ID,
                "messaging": [
                    {
                        "sender": {"id": USER_ID},
                        "recipient": {"id": PAGE_ID},
                        "timestamp": 1700000001000,
                        "message": {
                            "mid": "mid.fb456",
                            "text": "Privet, est tovar?",
                        },
                    }
                ],
            }
        ],
    }


# ── Normalizer tests ─────────────────────────────────────────────────────────

def test_ig_dm_normalised():
    msgs = parse_meta_webhook(
        make_ig_dm_payload(), TENANT_ID, CHANNEL_ID, "instagram"
    )
    assert len(msgs) == 1
    m = msgs[0]
    assert m.kind == "dm"
    assert m.platform == "instagram"
    assert m.external_user_id == USER_ID
    assert m.text == "Salom, mahsulot bormi?"
    assert m.external_message_id == "mid.abc123"


def test_ig_comment_normalised():
    msgs = parse_meta_webhook(
        make_ig_comment_payload(), TENANT_ID, CHANNEL_ID, "instagram"
    )
    assert len(msgs) == 1
    m = msgs[0]
    assert m.kind == "comment"
    assert m.platform == "instagram"
    assert m.external_user_id == USER_ID
    assert m.text == "Narxi qancha?"
    assert m.meta_extra is not None
    assert m.meta_extra["comment_id"] == COMMENT_ID
    assert m.meta_extra["sender_name"] == "Sardor"


def test_fb_dm_normalised():
    msgs = parse_meta_webhook(
        make_fb_dm_payload(), TENANT_ID, CHANNEL_ID, "facebook"
    )
    assert len(msgs) == 1
    m = msgs[0]
    assert m.kind == "dm"
    assert m.platform == "facebook"
    assert m.text == "Privet, est tovar?"


def test_own_page_message_skipped():
    """Messages from the page itself (echoes) should be ignored."""
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": PAGE_ID,
                "messaging": [
                    {
                        "sender": {"id": PAGE_ID},   # page sending to itself
                        "recipient": {"id": USER_ID},
                        "timestamp": 1700000000000,
                        "message": {"mid": "mid.echo", "text": "echo"},
                    }
                ],
            }
        ],
    }
    msgs = parse_meta_webhook(payload, TENANT_ID, CHANNEL_ID, "instagram")
    assert msgs == []


def test_comment_edit_ignored():
    """Verb != 'add' should be skipped."""
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": PAGE_ID,
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "item": "comment",
                            "verb": "edited",          # not 'add'
                            "comment_id": COMMENT_ID,
                            "from": {"id": USER_ID, "name": "Ali"},
                            "message": "edited text",
                            "created_time": 1700000000,
                        },
                    }
                ],
            }
        ],
    }
    msgs = parse_meta_webhook(payload, TENANT_ID, CHANNEL_ID, "instagram")
    assert msgs == []


def test_empty_payload_returns_no_messages():
    msgs = parse_meta_webhook(
        {"object": "instagram", "entry": []}, TENANT_ID, CHANNEL_ID, "instagram"
    )
    assert msgs == []


# ── InstagramDispatcher tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ig_comment_sends_public_and_private_reply():
    client = AsyncMock(spec=MetaGraphClient)
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)
    redis.setex = AsyncMock()

    dispatcher = InstagramDispatcher(client, redis)

    from worker.engine.unified import UnifiedMessage, MediaItem
    um = UnifiedMessage(
        tenant_id=TENANT_ID,
        platform="instagram",
        channel_id=CHANNEL_ID,
        kind="comment",
        external_user_id=USER_ID,
        conversation_id=f"instagram:{PAGE_ID}:comment:{COMMENT_ID}",
        text="Narxi qancha?",
        external_message_id=COMMENT_ID,
        meta_extra={"comment_id": COMMENT_ID, "page_id": PAGE_ID, "sender_name": "Sardor"},
    )

    await dispatcher.send_reply(um, "Narxi 50,000 so'm!", public_reply=True)

    client.reply_to_comment.assert_awaited_once_with(COMMENT_ID, "Narxi 50,000 so'm!")
    client.send_private_reply.assert_awaited_once_with(COMMENT_ID, "Narxi 50,000 so'm!")
    redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_ig_comment_private_reply_deduped():
    """Second reply to same comment should not send private DM."""
    client = AsyncMock(spec=MetaGraphClient)
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=1)  # already sent

    dispatcher = InstagramDispatcher(client, redis)

    from worker.engine.unified import UnifiedMessage
    um = UnifiedMessage(
        tenant_id=TENANT_ID,
        platform="instagram",
        channel_id=CHANNEL_ID,
        kind="comment",
        external_user_id=USER_ID,
        conversation_id=f"instagram:{PAGE_ID}:comment:{COMMENT_ID}",
        text="test",
        external_message_id=COMMENT_ID,
        meta_extra={"comment_id": COMMENT_ID, "page_id": PAGE_ID},
    )

    await dispatcher.send_reply(um, "Reply text", public_reply=True)

    client.reply_to_comment.assert_awaited_once()  # public reply still fires
    client.send_private_reply.assert_not_awaited()  # private DM skipped


@pytest.mark.asyncio
async def test_ig_dm_sends_direct_message():
    client = AsyncMock(spec=MetaGraphClient)
    redis = AsyncMock()

    dispatcher = InstagramDispatcher(client, redis)

    from worker.engine.unified import UnifiedMessage
    um = UnifiedMessage(
        tenant_id=TENANT_ID,
        platform="instagram",
        channel_id=CHANNEL_ID,
        kind="dm",
        external_user_id=USER_ID,
        conversation_id=f"instagram:{PAGE_ID}:{USER_ID}",
        text="hi",
        external_message_id="mid.dm1",
    )

    await dispatcher.send_reply(um, "Assalomu alaykum!")

    client.send_message.assert_awaited_once_with(USER_ID, "Assalomu alaykum!")


# ── FacebookDispatcher tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fb_dm_in_window_sends_response():
    client = AsyncMock(spec=MetaGraphClient)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"1")  # window is open

    dispatcher = FacebookDispatcher(client, redis, PAGE_ID)

    from worker.engine.unified import UnifiedMessage
    um = UnifiedMessage(
        tenant_id=TENANT_ID,
        platform="facebook",
        channel_id=CHANNEL_ID,
        kind="dm",
        external_user_id=USER_ID,
        conversation_id=f"facebook:{PAGE_ID}:{USER_ID}",
        text="hi",
        external_message_id="mid.fb1",
    )

    await dispatcher.send_reply(um, "Salom!")

    client.send_message.assert_awaited_once_with(USER_ID, "Salom!")
    client.send_message_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_fb_dm_outside_window_with_tag():
    client = AsyncMock(spec=MetaGraphClient)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)  # window closed

    dispatcher = FacebookDispatcher(client, redis, PAGE_ID)

    from worker.engine.unified import UnifiedMessage
    um = UnifiedMessage(
        tenant_id=TENANT_ID,
        platform="facebook",
        channel_id=CHANNEL_ID,
        kind="dm",
        external_user_id=USER_ID,
        conversation_id=f"facebook:{PAGE_ID}:{USER_ID}",
        text="order update",
        external_message_id="mid.fb2",
    )

    await dispatcher.send_reply(um, "Buyurtmangiz jo'natildi!", tag="POST_PURCHASE_UPDATE")

    client.send_message_tag.assert_awaited_once_with(
        USER_ID, "Buyurtmangiz jo'natildi!", "POST_PURCHASE_UPDATE"
    )
    client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_fb_dm_outside_window_no_tag_skipped():
    """Outside window with no tag: should log and skip, not raise."""
    client = AsyncMock(spec=MetaGraphClient)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)  # window closed

    dispatcher = FacebookDispatcher(client, redis, PAGE_ID)

    from worker.engine.unified import UnifiedMessage
    um = UnifiedMessage(
        tenant_id=TENANT_ID,
        platform="facebook",
        channel_id=CHANNEL_ID,
        kind="dm",
        external_user_id=USER_ID,
        conversation_id=f"facebook:{PAGE_ID}:{USER_ID}",
        text="any",
        external_message_id="mid.fb3",
    )

    await dispatcher.send_reply(um, "reply without tag")

    client.send_message.assert_not_awaited()
    client.send_message_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_fb_invalid_tag_raises():
    client = AsyncMock(spec=MetaGraphClient)
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)

    dispatcher = FacebookDispatcher(client, redis, PAGE_ID)

    from worker.engine.unified import UnifiedMessage
    um = UnifiedMessage(
        tenant_id=TENANT_ID,
        platform="facebook",
        channel_id=CHANNEL_ID,
        kind="dm",
        external_user_id=USER_ID,
        conversation_id="fb:conv",
        text="x",
        external_message_id="mid.fb4",
    )

    with pytest.raises(ValueError, match="Invalid FB message tag"):
        await dispatcher.send_reply(um, "text", tag="INVALID_TAG")


# ── MetaGraphClient signature test ───────────────────────────────────────────

def test_signature_verification_valid():
    import hmac as _hmac
    import hashlib as _hashlib

    app_secret = "mysecret"
    body = b'{"test": 1}'
    sig = "sha256=" + _hmac.new(
        app_secret.encode(), body, _hashlib.sha256
    ).hexdigest()

    client = MetaGraphClient("token", app_secret)
    assert client.verify_signature(body, sig) is True


def test_signature_verification_invalid():
    client = MetaGraphClient("token", "mysecret")
    assert client.verify_signature(b"body", "sha256=wrongsig") is False


def test_signature_verification_missing_prefix():
    client = MetaGraphClient("token", "mysecret")
    assert client.verify_signature(b"body", "badhash") is False
