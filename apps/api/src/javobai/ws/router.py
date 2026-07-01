"""
Phase 8 — realtime transport for the operator inbox.

Auth: the dashboard cannot rely on the HttpOnly JWT cookie being sent on a
direct browser→API websocket handshake — in local dev apps/web (:3000) and
apps/api (:8000) are different origins, and apps/web's BFF proxy can't relay a
persistent WebSocket through a Next.js Route Handler (see docs/ARCHITECTURE.md
§Decisions). Instead the browser:
  1. POSTs /auth/ws-ticket through the existing cookie-authenticated Next.js
     proxy, getting back a one-time, 60s ticket.
  2. Opens this websocket directly with `?ticket=...`.
The ticket is single-use (read + deleted on first use) and carries no more
privilege than "this user, for the next 60 seconds, may open one socket".

Fan-out: a single background task (started in main.py's lifespan) psubscribes
to `handoff:*` (Phase 5, apps/worker) and `events:*` (this phase, see
javobai.events) on Redis and rebroadcasts each message to every websocket
connected for that tenant.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from javobai.config import settings
from javobai.redis import get_redis
from javobai.ws.manager import Viewer, manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])


def _ticket_key(ticket: str) -> str:
    return f"ws_ticket:{ticket}"


@router.websocket("/ws/inbox")
async def ws_inbox(
    websocket: WebSocket,
    redis: Annotated[Redis, Depends(get_redis)],
    ticket: str | None = Query(default=None),
) -> None:
    if not ticket:
        await websocket.close(code=4401)
        return

    raw = await redis.get(_ticket_key(ticket))
    if not raw:
        await websocket.close(code=4401)
        return
    await redis.delete(_ticket_key(ticket))

    try:
        data = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
        tenant_id: str = data["tenant_id"]
        viewer = Viewer(user_id=data["user_id"], name=data.get("name") or data["user_id"])
    except (ValueError, KeyError):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    manager.connect(tenant_id, websocket, viewer)
    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                msg = json.loads(raw_msg)
            except ValueError:
                continue
            msg_type = msg.get("type")
            conversation_id = msg.get("conversation_id")
            if not conversation_id:
                continue
            if msg_type == "presence.join":
                await manager.set_presence(tenant_id, conversation_id, viewer, joined=True)
            elif msg_type == "presence.leave":
                await manager.set_presence(tenant_id, conversation_id, viewer, joined=False)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(tenant_id, websocket)


async def _listen() -> None:
    """Long-lived Redis subscriber, fanning handoff/event messages out to websockets."""
    redis: aioredis.Redis = aioredis.Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.psubscribe("handoff:*", "events:*")
    logger.info("Phase 8 event listener subscribed to handoff:* and events:*")
    try:
        async for message in pubsub.listen():
            if message.get("type") != "pmessage":
                continue
            channel: str = message["channel"]
            prefix, _, tenant_id = channel.partition(":")
            if not tenant_id:
                continue
            try:
                body = json.loads(message["data"])
            except ValueError:
                continue
            if prefix == "handoff":
                event_type = "handoff.created"
            else:
                event_type = body.pop("type", "message.created")
            await manager.broadcast(tenant_id, {"type": event_type, **body})
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 — the listener must never crash the API process silently
        logger.exception("Phase 8 event listener crashed")
    finally:
        await pubsub.aclose()  # type: ignore[no-untyped-call]
        await redis.aclose()


def start_event_listener() -> asyncio.Task[None]:
    return asyncio.create_task(_listen())


async def stop_event_listener(task: asyncio.Task[None]) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
