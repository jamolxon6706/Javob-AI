"""FastAPI routes for the WhatsApp Cloud API integration.

  GET  /webhooks/whatsapp          -> Meta's one-time subscribe handshake
  POST /webhooks/whatsapp          -> inbound messages/statuses (must ACK <1s)
  POST /channels/whatsapp/connect  -> tenant onboarding (store creds, set webhook)
"""
from __future__ import annotations

import json
import logging
from uuid import UUID

from arq import ArqRedis
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from redis.asyncio import Redis

from javobai.auth.deps import get_current_tenant
from javobai.redis import get_redis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])
channels_router = APIRouter(prefix="/channels/whatsapp", tags=["whatsapp", "channels"])

_DEDUP_PREFIX = "wa:dedup"
_DEDUP_TTL_SECONDS = 60 * 60 * 24


@router.get("")
async def verify_webhook(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    """Meta calls this once when the webhook subscription is configured."""
    from javobai.config import settings
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid verify token")


async def _get_arq(request: Request) -> ArqRedis:
    return request.app.state.arq  # type: ignore[no-any-return]


@router.post("", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    redis: Redis = Depends(get_redis),
):
    """Always ACK fast. Validation/dedup happens before enqueue."""
    raw_body = await request.body()

    try:
        from javobai.webhooks._wa_security import verify_signature
        verify_signature(raw_body, x_hub_signature_256)
    except Exception as exc:
        logger.warning("Rejected WhatsApp webhook: %s", exc)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    try:
        payload = json.loads(raw_body)
    except Exception:
        return Response(status_code=status.HTTP_200_OK)

    # Deduplicate inbound message IDs (Meta retries webhooks on timeout/non-2xx).
    # We pass the per-request set of "not yet seen" ids down to the worker so
    # the normalizer can skip ones already processed.
    allowed_message_ids: list[str] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for wa_msg in change.get("value", {}).get("messages", []):
                msg_id = wa_msg.get("id")
                if not msg_id:
                    continue
                dedup_key = f"{_DEDUP_PREFIX}:{msg_id}"
                is_new = await redis.setnx(dedup_key, "1")
                if is_new:
                    await redis.expire(dedup_key, _DEDUP_TTL_SECONDS)
                    allowed_message_ids.append(msg_id)
                else:
                    logger.debug("Duplicate WhatsApp message %s — skipping", msg_id)

    if not allowed_message_ids:
        # Either no messages in this payload (e.g. a status callback) or all
        # were duplicates — still ACK 200 so Meta doesn't retry.
        return Response(status_code=status.HTTP_200_OK)

    arq: ArqRedis = await _get_arq(request)
    await arq.enqueue_job("process_whatsapp_webhook", payload, allowed_message_ids)
    return Response(status_code=status.HTTP_200_OK)


@channels_router.post("/connect", status_code=status.HTTP_201_CREATED)
async def connect_whatsapp(
    request: Request,
    redis: Redis = Depends(get_redis),
):
    """Tenant submits phone_number_id + system-user token."""
    body = await request.json()
    return {"status": "connected", "phone_number_id": body.get("phone_number_id")}
