from datetime import datetime, timezone

from worker.engine.normalizer import normalize_telegram

_BASE_UPDATE = {
    "update_id": 100001,
    "message": {
        "message_id": 42,
        "from": {
            "id": 12345,
            "first_name": "Ali",
            "username": "ali_uz",
            "language_code": "uz",
            "is_bot": False,
        },
        "chat": {"id": 12345, "type": "private"},
        "date": 1718000000,
        "text": "Salom, qanday yordam berasiz?",
    },
}


def test_normalize_text_message() -> None:
    msg = normalize_telegram(
        _BASE_UPDATE,
        tenant_id="tenant-1",
        channel_id="channel-1",
        credentials_encrypted="enc",
    )
    assert msg is not None
    assert msg.platform == "telegram"
    assert msg.text == "Salom, qanday yordam berasiz?"
    assert msg.external_user_id == "12345"
    assert msg.chat_id == "12345"
    assert msg.conversation_id == "tg:channel-1:12345"
    assert msg.platform_msg_id == "42"
    assert msg.lang_hint == "uz"
    assert msg.kind == "dm"
    assert msg.media == []
    assert msg.received_at == datetime.fromtimestamp(1718000000, tz=timezone.utc)


def test_normalize_bot_message_returns_none() -> None:
    update = {
        "update_id": 100002,
        "message": {
            "message_id": 43,
            "from": {"id": 99, "first_name": "BotName", "is_bot": True},
            "chat": {"id": 99, "type": "private"},
            "date": 1718000000,
            "text": "I am a bot",
        },
    }
    msg = normalize_telegram(update, tenant_id="t1", channel_id="c1", credentials_encrypted="x")
    assert msg is None


def test_normalize_non_message_update_returns_none() -> None:
    # e.g. callback_query or channel_post without message
    update = {"update_id": 100003}
    msg = normalize_telegram(update, tenant_id="t1", channel_id="c1", credentials_encrypted="x")
    assert msg is None


def test_normalize_photo_message() -> None:
    update = {
        "update_id": 100004,
        "message": {
            "message_id": 44,
            "from": {"id": 12345, "first_name": "Ali", "is_bot": False},
            "chat": {"id": 12345, "type": "private"},
            "date": 1718000000,
            "caption": "Rasm",
            "photo": [
                {"file_id": "small", "file_size": 100, "width": 100, "height": 100},
                {"file_id": "large", "file_size": 5000, "width": 800, "height": 600},
            ],
        },
    }
    msg = normalize_telegram(update, tenant_id="t1", channel_id="c1", credentials_encrypted="x")
    assert msg is not None
    assert len(msg.media) == 1
    assert msg.media[0].type == "image"
    assert msg.media[0].url == "large"
    assert msg.text == "Rasm"
