"""
FastAPI webhook router for Instagram and Facebook.

Endpoints:
  GET  /webhooks/meta          — hub.challenge verification (shared for IG + FB)
  POST /webhooks/instagram     — IG events (DMs, comments)
  POST /webhooks/facebook      — FB Messenger events
  POST /channels/meta/connect  — onboard a new IG/FB page channel
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Annotated, Any
from uuid import UUID

import arq
import arq.connections
import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.deps import get_current_tenant
from javobai.config import settings
from javobai.crypto import encrypt as encrypt_credential
from javobai.db.models.channel import Channel
from javobai.db.session import get_db
from javobai.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks-meta"])


# ── Hub verification ──────────────────────────────────────────────────────

@router.get("/webhooks/meta")
async def meta_webhook_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """Meta sends GET with hub.challenge during webhook setup."""
    if hub_mode != "subscribe" or hub_verify_token != settings.meta_verify_token:
        raise HTTPException(status_code=403, detail="Verification failed")
    return int(hub_challenge)


# ── Instagram webhook ───────────────────────────────────────────────────────

@router.post("/webhooks/instagram", status_code=status.HTTP_200_OK)
async def instagram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    raw_body = await request.body()
    _verify_meta_signature(raw_body, x_hub_signature_256)

    payload = json.loads(raw_body)
    if payload.get("object") != "instagram":
        return {"status": "ignored"}

    background_tasks.add_task(_ingest_meta_events, payload, "instagram", db, redis)
    return {"status": "ok"}


# ── Facebook Messenger webhook ───────────────────────────────────────────────

@router.post("/webhooks/facebook", status_code=status.HTTP_200_OK)
async def facebook_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    raw_body = await request.body()
    _verify_meta_signature(raw_body, x_hub_signature_256)

    payload = json.loads(raw_body)
    if payload.get("object") != "page":
        return {"status": "ignored"}

    background_tasks.add_task(_ingest_meta_events, payload, "facebook", db, redis)
    return {"status": "ok"}


# ── Channel onboarding ──────────────────────────────────────────────────────

@router.post("/channels/meta/connect", status_code=status.HTTP_201_CREATED)
async def connect_meta_channel(
    request: Request,
    db: AsyncSession = Depends(get_db),
    tenant=Depends(get_current_tenant),
):
    """Onboard an Instagram or Facebook page channel."""
    body = await request.json()
    platform = body.get("platform", "instagram")
    access_token = body.get("access_token", "")
    page_id = body.get("page_id", "")
    page_name = body.get("page_name", "")

    channel = Channel(
        tenant_id=tenant.id,
        platform=platform,
        external_id=page_id,
        name=page_name,
        credentials=encrypt_credential(
            json.dumps({"access_token": access_token, "page_id": page_id})
        ),
        is_active=True,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)

    return {
        "id": str(channel.id),
        "platform": platform,
        "page_id": page_id,
        "page_name": page_name,
        "status": "connected",
    }


# ── Internal helpers ────────────────────────────────────────────────────────

def _verify_meta_signature(raw_body: bytes, sig_header: str | None) -> None:
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing X-Hub-Signature-256")
    if not sig_header.startswith("sha256="):
        raise HTTPException(status_code=400, detail="Invalid signature format")
    expected = hmac.new(
        settings.meta_app_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    received = sig_header[7:]
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=403, detail="Signature mismatch")


async def _ingest_meta_events(
    payload: dict[str, Any],
    platform: str,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> None:
    """Background task: resolve channel, normalise events, push to ARQ queue."""
    page_ids: set[str] = set()
    for entry in payload.get("entry", []):
        if entry.get("id"):
            page_ids.add(entry["id"])

    if not page_ids:
        return

    result = await db.execute(
        select(Channel).where(
            Channel.external_id.in_(page_ids),
            Channel.platform == platform,
            Channel.is_active == True,  # noqa: E712
        )
    )
    channels = {ch.external_id: ch for ch in result.scalars().all()}

    if not channels:
        logger.warning("Meta webhook (%s): no active channel for page_ids=%s", platform, page_ids)
        return

    pool = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))

    for entry in payload.get("entry", []):
        page_id = entry.get("id", "")
        channel = channels.get(page_id)
        if not channel:
            continue

        for messaging in entry.get("messaging", []):
            msg_id = messaging.get("message", {}).get("mid", "")
            if not msg_id:
                continue

            dedup_key = f"dedup:{platform}:{msg_id}"
            is_new = await redis.setnx(dedup_key, "1")
            if not is_new:
                continue
            await redis.expire(dedup_key, 86400)

            if platform == "facebook":
                window_key = f"window:facebook:{channel.id}"
                await redis.setex(window_key, 86400, "1")

            await pool.enqueue_job(
                "process_meta_message",
                {
                    "kind": "dm",
                    "platform": platform,
                    "channel_id": str(channel.id),
                    "tenant_id": str(channel.tenant_id),
                    "raw": messaging,
                },
            )

        # IG/FB comments (Phase 10: public comment -> optional public reply +
        # one private-reply DM). Only "add" events on comments/posts matter.
        for change in entry.get("changes", []):
            if change.get("field") not in ("comments", "feed"):
                continue
            value = change.get("value", {})
            comment_id = value.get("comment_id") or value.get("id", "")
            if not comment_id or value.get("verb") != "add":
                continue

            dedup_key = f"dedup:{platform}:comment:{comment_id}"
            is_new = await redis.setnx(dedup_key, "1")
            if not is_new:
                continue
            await redis.expire(dedup_key, 86400)

            await pool.enqueue_job(
                "process_meta_message",
                {
                    "kind": "comment",
                    "platform": platform,
                    "channel_id": str(channel.id),
                    "tenant_id": str(channel.tenant_id),
                    "page_id": page_id,
                    "raw": value,
                },
            )

    await pool.aclose()
