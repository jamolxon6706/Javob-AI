"""Outbound WhatsApp Cloud API adapter.

Used by the dispatcher (Phase 5) as the WhatsApp-specific implementation of
the generic per-platform send interface. Enforces:
  - free-form text only inside the 24h customer-service window,
  - template-only sends outside it, validated against the tenant's
    WhatsAppTemplate registry (must be status=APPROVED),
  - basic retry on 5xx/429 (the generic rate-limiter from Phase 5 wraps this
    further; this module focuses on the Meta Graph API call shape itself).
"""
from __future__ import annotations

import logging

import httpx
from redis.asyncio import Redis

from worker.settings import settings
from worker.adapters.whatsapp.window import is_window_open

logger = logging.getLogger(__name__)


class TemplateRequiredError(Exception):
    """Raised when a free-form send is attempted outside the 24h window."""

    def __init__(self, channel_id: str, external_user_id: str):
        self.channel_id = channel_id
        self.external_user_id = external_user_id
        super().__init__(
            f"24h window closed for {external_user_id} on channel {channel_id}; "
            "an approved template is required."
        )


class TemplateNotApprovedError(Exception):
    def __init__(self, template_name: str):
        super().__init__(f"Template '{template_name}' is not APPROVED for sending.")


class WhatsAppAdapter:
    def __init__(self, *, phone_number_id: str, access_token: str, redis: Redis):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.redis = redis
        # NOTE: previously written as an f-string with same-quote nested
        # strings (f"{"..."}"), which is a SyntaxError on Python < 3.12.
        # The Dockerfile pins python:3.11-slim, so this broke the import of
        # this entire module (and everything that imports it, e.g.
        # tasks/whatsapp.py) before any code in it could even run.
        self._base_url = (
            f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def send_text(self, *, channel_id: str, to: str, text: str) -> dict:
        """Free-form text send. Only valid inside the 24h window."""
        if not await is_window_open(self.redis, channel_id, to):
            raise TemplateRequiredError(channel_id, to)

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": False},
        }
        return await self._post(payload)

    async def send_template(
        self,
        *,
        to: str,
        template,  # app.models.whatsapp_template.WhatsAppTemplate
        parameters: list[str] | None = None,
    ) -> dict:
        """Template send. Allowed regardless of window state — this is the
        ONLY legal way to (re-)open a conversation once the window has
        closed."""
        if not template.is_usable():
            raise TemplateNotApprovedError(template.name)

        components = []
        if parameters:
            components.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": p} for p in parameters],
                }
            )

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template.name,
                "language": {"code": template.language},
                "components": components,
            },
        }
        return await self._post(payload)

    async def _post(self, payload: dict, *, _retries: int = 3) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            for attempt in range(1, _retries + 1):
                resp = await client.post(self._base_url, headers=self._headers, json=payload)
                if resp.status_code < 300:
                    return resp.json()

                retryable = resp.status_code == 429 or resp.status_code >= 500
                if not retryable or attempt == _retries:
                    logger.error(
                        "WhatsApp send failed (status=%s, attempt=%s): %s",
                        resp.status_code,
                        attempt,
                        resp.text,
                    )
                    resp.raise_for_status()

                # Exponential backoff handled by the caller's rate-limiter
                # (Phase 5 dead-letter/backoff queue); here we just bubble
                # the retryable failure up after exhausting local attempts.
                logger.warning(
                    "WhatsApp send retryable failure (status=%s), attempt %s/%s",
                    resp.status_code,
                    attempt,
                    _retries,
                )
        raise RuntimeError("unreachable")
