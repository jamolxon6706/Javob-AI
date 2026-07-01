"""
Instagram outbound dispatcher.

Comment flow:
  1. Public reply to the comment (optional, configurable).
  2. ONE private DM to the commenter (within 7 days, 1 per comment).

DM flow:
  - Send free-form within 24h window (tracked by Faza 5 WindowTracker).
  - Outside window: refuse (IG has no template API like WA).

Dedup guard for private replies is stored in Redis:
  Key: ig_private_reply:{comment_id}  TTL: 7 days
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import redis.asyncio as aioredis

from worker.adapters.meta.client import MetaGraphClient, MetaAPIError
from worker.engine.unified import UnifiedMessage

logger = logging.getLogger(__name__)

PRIVATE_REPLY_TTL = int(timedelta(days=7).total_seconds())

REQUIRED_IG_PERMISSIONS = [
    "instagram_basic",
    "instagram_manage_messages",
    "instagram_manage_comments",
    "pages_read_engagement",
]


class InstagramDispatcher:
    def __init__(self, client: MetaGraphClient, redis: aioredis.Redis):
        self._client = client
        self._redis = redis

    async def send_reply(
        self,
        original: UnifiedMessage,
        text: str,
        *,
        public_reply: bool = True,
    ) -> None:
        """
        Send a reply for a DM or comment.
        For comments: public + one private DM (deduped).
        For DMs: direct message within 24h window.
        """
        if original.kind == "dm":
            await self._send_dm(original.external_user_id, text)
        elif original.kind == "comment":
            await self._handle_comment_reply(original, text, public_reply)

    async def _send_dm(self, user_id: str, text: str) -> None:
        try:
            await self._client.send_message(user_id, text)
            logger.info("IG DM sent to %s", user_id)
        except MetaAPIError as e:
            logger.error("IG DM failed: %s", e)
            raise

    async def _handle_comment_reply(
        self,
        original: UnifiedMessage,
        text: str,
        public_reply: bool,
    ) -> None:
        meta = original.meta_extra or {}
        comment_id = meta.get("comment_id", "")
        sender_id = original.external_user_id

        # 1. Public reply
        if public_reply and comment_id:
            try:
                await self._client.reply_to_comment(comment_id, text)
                logger.info("IG public reply posted on comment %s", comment_id)
            except MetaAPIError as e:
                logger.warning("IG public reply failed (non-fatal): %s", e)

        # 2. Private DM — enforce 1 per comment using Redis dedup
        if comment_id:
            dedup_key = f"ig_private_reply:{comment_id}"
            already_sent = await self._redis.exists(dedup_key)
            if already_sent:
                logger.info(
                    "IG private reply skipped (already sent) for comment %s",
                    comment_id,
                )
                return

            try:
                await self._client.send_private_reply(comment_id, text)
                await self._redis.setex(dedup_key, PRIVATE_REPLY_TTL, "1")
                logger.info("IG private DM sent for comment %s", comment_id)
            except MetaAPIError as e:
                # Error code 10 = permission not granted; code 100 = already replied
                if e.code in (10, 100):
                    logger.warning("IG private reply blocked by Meta (%s): %s", e.code, e)
                else:
                    logger.error("IG private reply error: %s", e)
                    raise

    async def check_permissions(self) -> None:
        await self._client.check_permissions(REQUIRED_IG_PERMISSIONS)
