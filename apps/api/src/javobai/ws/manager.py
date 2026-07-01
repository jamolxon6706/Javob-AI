"""
Phase 8 — in-process WebSocket connection registry.

Single-instance assumption (see docs/ARCHITECTURE.md §Decisions): the
connection set and the "who is viewing this conversation" presence map live
in this process's memory. That's the simplest reversible option for a single
API instance. If/when the API scales to multiple instances behind a load
balancer, presence needs to move to Redis (e.g. a per-conversation Redis set
with short-TTL heartbeats) so viewers are visible across instances — the
Redis pub/sub fan-out for handoff/message events already scales horizontally
as-is, only this in-memory presence map does not.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Viewer:
    user_id: str
    name: str


class ConnectionManager:
    def __init__(self) -> None:
        # tenant_id -> {websocket: viewer}
        self._connections: dict[str, dict[WebSocket, Viewer]] = defaultdict(dict)
        # tenant_id -> conversation_id -> viewers currently looking at it
        self._presence: dict[str, dict[str, set[Viewer]]] = defaultdict(lambda: defaultdict(set))

    def connect(self, tenant_id: str, ws: WebSocket, viewer: Viewer) -> None:
        self._connections[tenant_id][ws] = viewer

    async def disconnect(self, tenant_id: str, ws: WebSocket) -> None:
        viewer = self._connections.get(tenant_id, {}).pop(ws, None)
        if viewer is None:
            return
        # Drop this viewer from any conversation they were looking at, and
        # tell the rest of the tenant's connected operators.
        for conversation_id, viewers in list(self._presence.get(tenant_id, {}).items()):
            if viewer in viewers:
                viewers.discard(viewer)
                await self.broadcast(
                    tenant_id,
                    {
                        "type": "presence.update",
                        "conversation_id": conversation_id,
                        "viewers": [v.name for v in viewers],
                    },
                )

    async def set_presence(
        self, tenant_id: str, conversation_id: str, viewer: Viewer, *, joined: bool
    ) -> None:
        viewers = self._presence[tenant_id][conversation_id]
        if joined:
            viewers.add(viewer)
        else:
            viewers.discard(viewer)
        await self.broadcast(
            tenant_id,
            {
                "type": "presence.update",
                "conversation_id": conversation_id,
                "viewers": [v.name for v in viewers],
            },
        )

    async def broadcast(self, tenant_id: str, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(tenant_id, {})):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 — one broken socket shouldn't break the rest
                dead.append(ws)
        for ws in dead:
            await self.disconnect(tenant_id, ws)


# Module-level singleton — one registry per API process (see class docstring).
manager = ConnectionManager()
