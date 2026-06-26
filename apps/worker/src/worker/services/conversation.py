from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Conversation.status values that mean "a human is already handling this — don't auto-reply"
_BOT_INACTIVE_STATUSES = {"waiting_operator", "bot_silenced"}


@dataclass(frozen=True)
class ConversationState:
    id: str
    status: str
    window_expires_at: datetime | None
    bot_silenced_until: datetime | None


def is_bot_active(conversation: ConversationState) -> bool:
    """Operator-active check (ARCHITECTURE.md §Core Engine step 2)."""
    if conversation.status in _BOT_INACTIVE_STATUSES:
        return False
    if conversation.bot_silenced_until is not None:
        if datetime.now(timezone.utc) < conversation.bot_silenced_until:
            return False
    return True


async def get_or_create_contact(
    conn: object,  # asyncpg.Connection
    tenant_id: str,
    platform: str,
    external_user_id: str,
) -> str:
    row = await conn.fetchrow(  # type: ignore[attr-defined]
        """
        INSERT INTO contacts (id, tenant_id, external_user_id, platform, created_at, updated_at)
        VALUES ($1, $2, $3, $4, NOW(), NOW())
        ON CONFLICT (tenant_id, platform, external_user_id)
        DO UPDATE SET updated_at = NOW()
        RETURNING id
        """,
        str(uuid.uuid4()),
        tenant_id,
        external_user_id,
        platform,
    )
    return str(row["id"])


async def get_or_create_conversation(
    conn: object,  # asyncpg.Connection
    tenant_id: str,
    channel_id: str,
    contact_id: str,
) -> ConversationState:
    row = await conn.fetchrow(  # type: ignore[attr-defined]
        """
        INSERT INTO conversations (id, tenant_id, channel_id, contact_id, status, created_at, updated_at)
        VALUES ($1, $2, $3, $4, 'open', NOW(), NOW())
        ON CONFLICT (channel_id, contact_id)
        DO UPDATE SET updated_at = NOW()
        RETURNING id, status, window_expires_at, bot_silenced_until
        """,
        str(uuid.uuid4()),
        tenant_id,
        channel_id,
        contact_id,
    )
    return ConversationState(
        id=str(row["id"]),
        status=str(row["status"]),
        window_expires_at=row["window_expires_at"],
        bot_silenced_until=row["bot_silenced_until"],
    )


async def save_message(
    conn: object,  # asyncpg.Connection
    *,
    conversation_id: str,
    tenant_id: str,
    direction: str,
    content: str,
    platform_msg_id: str | None = None,
    source: str | None = None,
    rag_score: float | None = None,
) -> None:
    await conn.execute(  # type: ignore[attr-defined]
        """
        INSERT INTO messages
            (id, conversation_id, tenant_id, direction, content, media,
             platform_msg_id, source, rag_score, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, '[]', $6, $7, $8, NOW(), NOW())
        """,
        str(uuid.uuid4()),
        conversation_id,
        tenant_id,
        direction,
        content,
        platform_msg_id,
        source,
        rag_score,
    )


async def extend_window(conn: object, conversation_id: str, hours: int = 24) -> None:
    """Reset the 24h customer-service messaging window after an inbound message."""
    await conn.execute(  # type: ignore[attr-defined]
        """
        UPDATE conversations
        SET window_expires_at = NOW() + ($2 || ' hours')::interval, updated_at = NOW()
        WHERE id = $1
        """,
        conversation_id,
        str(hours),
    )


async def mark_handoff(conn: object, conversation_id: str) -> None:
    """Flag a conversation for human pickup; the bot stays silent until an operator resolves it."""
    await conn.execute(  # type: ignore[attr-defined]
        """
        UPDATE conversations
        SET status = 'waiting_operator', updated_at = NOW()
        WHERE id = $1
        """,
        conversation_id,
    )
