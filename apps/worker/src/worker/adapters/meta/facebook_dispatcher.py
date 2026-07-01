"""
Facebook Messenger outbound dispatcher.

Window rules:
  - Within 24h of last inbound: free-form RESPONSE type.
  - Outside window: only MESSAGE_TAG allowed (CONFIRMED_EVENT_UPDATE,
    POST_PURCHASE_UPDATE, ACCOUNT_UPDATE, HUMAN_AGENT).
  - Window tracked by Faza 5 WindowTracker (Redis key per conversation).

Message tag awareness:
  - Dispatcher checks window tracker before sending.
  - If outside window: caller must supply a tag or send fails gracefully.
"""
from __future__ import annotations

import logging

import redis.asyncio as aioredis

from worker.adapters.meta.client import MetaGraphClient, MetaAPIError
from worker.engine.unified import UnifiedMessage

logger = logging.getLogger(__name__)

REQUIRED_FB_PERMISSIONS = [
    "pages_messaging",
    "pages_read_engagement",
    "pages_manage_metadata",
]

# Valid message tags for outside-window FB sends
VALID_TAGS = {
    "CONFIRMED_EVENT_UPDATE",
    "POST_PURCHASE_UPDATE",
    "ACCOUNT_UPDATE",
    "HUMAN_AGENT",
}


class FacebookDispatcher:
    def __init__(
        self,
        client: MetaGraphClient,
        redis: aioredis.Redis,
        page_id: str,
    ):
        self._client = client
        self._redis = redis
        self._page_id = page_id

    async def send_reply(
        self,
        original: UnifiedMessage,
        text: str,
        *,
        tag: str | None = None,
    ) -> None:
        """
        Send a reply to a FB Messenger DM.
        Checks window and applies tag if outside 24h.
        """
        window_key = f"window:facebook:{original.conversation_id}"
        window_ts = await self._redis.get(window_key)
        in_window = bool(window_ts)

        if in_window:
            await self._send_response(original.external_user_id, text)
        else:
            if not tag:
                logger.warning(
                    "FB Messenger: outside 24h window for %s, no tag supplied — skipping",
                    original.conversation_id,
                )
                return
            if tag not in VALID_TAGS:
                raise ValueError(f"Invalid FB message tag: {tag}")
            await self._send_tagged(original.external_user_id, text, tag)

    async def _send_response(self, recipient_id: str, text: str) -> None:
        try:
            await self._client.send_message(recipient_id, text)
            logger.info("FB Messenger RESPONSE sent to %s", recipient_id)
        except MetaAPIError as e:
            logger.error("FB Messenger send failed: %s", e)
            raise

    async def _send_tagged(
        self, recipient_id: str, text: str, tag: str
    ) -> None:
        try:
            await self._client.send_message_tag(recipient_id, text, tag)
            logger.info(
                "FB Messenger MESSAGE_TAG (%s) sent to %s", tag, recipient_id
            )
        except MetaAPIError as e:
            logger.error("FB Messenger tagged send failed: %s", e)
            raise

    async def check_permissions(self) -> None:
        await self._client.check_permissions(REQUIRED_FB_PERMISSIONS)
