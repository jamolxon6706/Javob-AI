"""
Meta Graph API shared client.
Handles token management, permission checks, and raw API calls
for both Instagram and Facebook Messenger adapters.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v19.0"


class MetaPermissionError(Exception):
    """Raised when required App Review permissions are missing."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Missing Meta permissions: {missing}")


class MetaAPIError(Exception):
    """Raised on non-200 responses from Graph API."""

    def __init__(self, code: int, message: str, subcode: int | None = None):
        self.code = code
        self.subcode = subcode
        super().__init__(f"Meta API error {code}: {message}")


class MetaGraphClient:
    """
    Thin async wrapper around Meta Graph API.
    One instance per channel (holds the page/user access token).
    """

    def __init__(self, access_token: str, app_secret: str):
        self._token = access_token
        self._app_secret = app_secret

    # ── Signature verification ──────────────────────────────────────────────

    def verify_signature(self, raw_body: bytes, sig_header: str) -> bool:
        """
        Verify X-Hub-Signature-256 header.
        sig_header format: "sha256=<hex>"
        """
        if not sig_header.startswith("sha256="):
            return False
        expected = hmac.new(
            self._app_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        received = sig_header[7:]
        return hmac.compare_digest(expected, received)

    # ── Generic request ─────────────────────────────────────────────────────

    async def get(self, path: str, **params: Any) -> dict:
        params["access_token"] = self._token
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{GRAPH_BASE}{path}", params=params)
            return self._handle(r)

    async def post(self, path: str, json: dict | None = None, **params: Any) -> dict:
        params["access_token"] = self._token
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{GRAPH_BASE}{path}", json=json or {}, params=params
            )
            return self._handle(r)

    def _handle(self, r: httpx.Response) -> dict:
        data = r.json()
        if "error" in data:
            err = data["error"]
            raise MetaAPIError(
                err.get("code", 0),
                err.get("message", "unknown"),
                err.get("error_subcode"),
            )
        return data

    # ── Permission check ────────────────────────────────────────────────────

    async def check_permissions(self, required: list[str]) -> None:
        """
        Raises MetaPermissionError if any required permission is not granted.
        """
        data = await self.get("/me/permissions")
        granted = {
            p["permission"]
            for p in data.get("data", [])
            if p.get("status") == "granted"
        }
        missing = [p for p in required if p not in granted]
        if missing:
            raise MetaPermissionError(missing)

    # ── Messaging ───────────────────────────────────────────────────────────

    async def send_message(self, recipient_id: str, text: str) -> dict:
        return await self.post(
            "/me/messages",
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": text},
                "messaging_type": "RESPONSE",
            },
        )

    async def send_message_tag(
        self, recipient_id: str, text: str, tag: str
    ) -> dict:
        """Send outside 24h window using a message tag (FB Messenger only)."""
        return await self.post(
            "/me/messages",
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": text},
                "messaging_type": "MESSAGE_TAG",
                "tag": tag,
            },
        )

    # ── Instagram comment ───────────────────────────────────────────────────

    async def reply_to_comment(self, comment_id: str, text: str) -> dict:
        """Post a public reply to an IG comment."""
        return await self.post(f"/{comment_id}/replies", json={"message": text})

    async def send_private_reply(self, comment_id: str, text: str) -> dict:
        """
        Send ONE private DM in reply to an IG comment.
        Respects: 1 DM per comment, within 7 days.
        """
        return await self.post(
            "/me/messages",
            json={
                "recipient": {"comment_id": comment_id},
                "message": {"text": text},
                "messaging_type": "RESPONSE",
            },
        )

    # ── Webhook subscription ────────────────────────────────────────────────

    async def subscribe_page_to_app(self, page_id: str) -> dict:
        return await self.post(
            f"/{page_id}/subscribed_apps",
            json={"subscribed_fields": ["messages", "messaging_postbacks", "feed"]},
        )

    async def get_me(self) -> dict:
        return await self.get("/me", fields="id,name,username")
