"""WhatsApp Cloud API webhook signature verification (API-side).

This mirrors worker/src/worker/adapters/whatsapp/security.py, but lives in
the `javobai` (apps/api) package because apps/api and apps/worker are
separate installable packages (no shared import path between them) and the
webhook route in javobai/webhooks/whatsapp.py needs this at the API layer,
before the payload is ever handed to ARQ/the worker.

BUG FIX: javobai/webhooks/whatsapp.py was importing
`javobai.webhooks._wa_security`, which never existed in this package. That
ImportError was silently caught by the surrounding `except Exception` and
turned into an HTTP 403 — meaning every single WhatsApp webhook delivery
(valid or not) was rejected before reaching the dedup/enqueue logic.
"""
from __future__ import annotations

import hashlib
import hmac

from javobai.config import settings


class InvalidSignatureError(Exception):
    """Raised when the X-Hub-Signature-256 header does not match the body."""


def verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    """Raise InvalidSignatureError if `signature_header` doesn't match.

    `signature_header` is the full `X-Hub-Signature-256` header value,
    e.g. "sha256=7f3c...". Verified against settings.whatsapp_app_secret —
    NOT settings.meta_app_secret, which is a separate Meta app/secret used
    only for the Instagram/Facebook webhook (see webhooks/meta.py).
    """
    if not signature_header or not signature_header.startswith("sha256="):
        raise InvalidSignatureError("Missing or malformed X-Hub-Signature-256 header")

    received_digest = signature_header.removeprefix("sha256=")
    expected_digest = hmac.new(
        key=settings.whatsapp_app_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(received_digest, expected_digest):
        raise InvalidSignatureError("X-Hub-Signature-256 mismatch")
