from datetime import datetime, timezone

from .unified import MediaItem, UnifiedMessage


def _tg_user_id(update: dict) -> str:  # type: ignore[type-arg]
    msg = update.get("message") or update.get("edited_message") or {}
    sender = msg.get("from", {})
    return str(sender.get("id", "unknown"))


def _tg_chat_id(update: dict) -> str:  # type: ignore[type-arg]
    msg = update.get("message") or update.get("edited_message") or {}
    return str(msg.get("chat", {}).get("id", "unknown"))


def _tg_text(update: dict) -> str:  # type: ignore[type-arg]
    msg = update.get("message") or update.get("edited_message") or {}
    return msg.get("text") or msg.get("caption") or ""


def _tg_media(update: dict) -> list[MediaItem]:  # type: ignore[type-arg]
    msg = update.get("message") or {}
    items: list[MediaItem] = []
    if msg.get("photo"):
        # Telegram sends multiple sizes; take the largest
        largest = max(msg["photo"], key=lambda p: p.get("file_size", 0))
        items.append(MediaItem(type="image", url=largest.get("file_id", ""), mime_type="image/jpeg"))
    if msg.get("video"):
        items.append(MediaItem(type="video", url=msg["video"].get("file_id", ""), mime_type="video/mp4"))
    if msg.get("audio"):
        items.append(MediaItem(type="audio", url=msg["audio"].get("file_id", ""), mime_type="audio/mpeg"))
    if msg.get("document"):
        items.append(MediaItem(type="document", url=msg["document"].get("file_id", ""), mime_type=None))
    if msg.get("voice"):
        items.append(MediaItem(type="audio", url=msg["voice"].get("file_id", ""), mime_type="audio/ogg"))
    return items


def normalize_telegram(
    update: dict,  # type: ignore[type-arg]
    *,
    tenant_id: str,
    channel_id: str,
    credentials_encrypted: str,
) -> UnifiedMessage | None:
    """Convert a raw Telegram Update dict to a UnifiedMessage.

    Returns None if the update doesn't contain a user-sent message
    (e.g. channel posts, service messages, etc.).
    """
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None

    sender = msg.get("from")
    if not sender or sender.get("is_bot"):
        return None

    chat_id = str(msg.get("chat", {}).get("id", ""))
    user_id = str(sender.get("id", ""))
    message_id = str(msg.get("message_id", ""))
    date = msg.get("date", 0)

    return UnifiedMessage(
        tenant_id=tenant_id,
        platform="telegram",
        channel_id=channel_id,
        kind="dm",
        external_user_id=user_id,
        conversation_id=f"tg:{channel_id}:{chat_id}",
        text=_tg_text(update),
        media=_tg_media(update),
        lang_hint=sender.get("language_code"),
        raw=update,
        received_at=datetime.fromtimestamp(date, tz=timezone.utc),
        credentials_encrypted=credentials_encrypted,
        chat_id=chat_id,
    )
