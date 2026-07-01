"""Security helpers for the WhatsApp Cloud API webhook.

Meta signs every webhook POST body with the app secret using HMAC-SHA256,
delivered in the `X-Hub-Signature-256` header as `sha256=<hex>`.
The GET verification handshake instead checks a static `hub.verify_token`
that the tenant (or platform owner, for the shared app) configured in the
Meta App Dashboard.
"""
from __future__ import annotations

import hashlib
import hmac

from worker.settings import settings


class InvalidSignatureError(Exception):
    """Raised when the X-Hub-Signature-256 header does not match the body."""


def verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    """Raise InvalidSignatureError if `signature_header` doesn't match.

    `signature_header` is the full `X-Hub-Signature-256` header value,
    e.g. "sha256=7f3c...".
    """
    if not signature_header or not signature_header.startswith("sha256="):
        raise InvalidSignatureError("Missing or malformed X-Hub-Signature-256 header")

    received_digest = signature_header.removeprefix("sha256=")
    # BUG FIX: this must be verified against the WhatsApp app secret, not the
    # Meta (IG/FB) app secret — they are configured separately
    # (settings.whatsapp_app_secret vs settings.meta_app_secret) and using the
    # wrong one means every legitimate WhatsApp webhook fails verification.
    expected_digest = hmac.new(
        key=settings.whatsapp_app_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(received_digest, expected_digest):
        raise InvalidSignatureError("X-Hub-Signature-256 mismatch")


def verify_handshake_token(mode: str | None, token: str | None) -> bool:
    """Used for the GET /webhooks/whatsapp subscribe handshake."""
    # BUG FIX: settings.META_WEBHOOK_VERIFY_TOKEN does not exist on
    # WorkerSettings (AttributeError at call time); the real field is
    # whatsapp_verify_token.
    return mode == "subscribe" and token == settings.whatsapp_verify_token
