"""FlowTrigger: checks which flows should run for an incoming message.

Called from CoreEngine.process(), before the RAG step, so a matched flow
short-circuits the FAQ/LLM/action pipeline entirely (ARCHITECTURE.md
§Core Engine — flow trigger runs first).

BUG FIX (Band 8): this previously referenced an unimported `Flow` model and
used a SQLAlchemy AsyncSession, but nothing in the worker ever constructed a
FlowTrigger or called match_and_run — flows were saved by the dashboard but
never executed. Rewritten on asyncpg (matching CoreEngine/conversation.py)
and wired into CoreEngine.process().
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional
from uuid import UUID

from worker.engine.unified import UnifiedMessage
from worker.services.flow_engine import FlowContext, FlowEngine

logger = logging.getLogger(__name__)


def _as_json(value: Any, default: Any) -> Any:
    """asyncpg returns json/jsonb columns as raw text unless a codec is
    registered (none is, in worker/main.py's startup()); parse defensively
    so this works whether or not that ever changes."""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class FlowTrigger:
    """Stateless — takes the asyncpg connection per call, like CoreEngine."""

    async def _fetch_candidate_flows(
        self, conn: object, tenant_id: UUID
    ) -> list[dict[str, Any]]:
        rows = await conn.fetch(  # type: ignore[attr-defined]
            """
            SELECT id, trigger_type, trigger_config, nodes, edges
            FROM flows
            WHERE tenant_id = $1
              AND is_active = true
              AND trigger_type IN ('first_contact', 'keyword')
            """,
            tenant_id,
        )
        flows = []
        for r in rows:
            d = dict(r)
            d["trigger_config"] = _as_json(d.get("trigger_config"), {})
            d["nodes"] = _as_json(d.get("nodes"), [])
            d["edges"] = _as_json(d.get("edges"), [])
            flows.append(d)
        return flows

    async def _is_first_contact(self, conn: object, conversation_id: str) -> bool:
        """True iff the message that triggered this run is the only inbound
        message in the conversation so far (CoreEngine.process is always
        called after save_message() has already persisted the current
        inbound message, so count == 1 means "brand new conversation")."""
        row = await conn.fetchrow(  # type: ignore[attr-defined]
            "SELECT count(*) AS n FROM messages WHERE conversation_id = $1",
            conversation_id,
        )
        return bool(row) and row["n"] <= 1

    async def match_and_run(
        self,
        message: UnifiedMessage,
        conn: object,  # asyncpg.Connection
    ) -> Optional[list[str]]:
        """Returns list of messages to send if a flow matched, else None.

        Priority: first_contact > keyword. Only runs ONE flow per message.
        """
        tenant_id = UUID(str(message.tenant_id))
        flows = await self._fetch_candidate_flows(conn, tenant_id)
        if not flows:
            return None

        is_new = await self._is_first_contact(conn, message.conversation_id)

        matched: dict[str, Any] | None = None
        for flow in flows:
            if flow["trigger_type"] == "first_contact" and is_new:
                matched = flow
                break
        if matched is None:
            text_lower = (message.text or "").lower()
            for flow in flows:
                if flow["trigger_type"] != "keyword":
                    continue
                keywords = (flow.get("trigger_config") or {}).get("keywords", [])
                if any(str(kw).lower() in text_lower for kw in keywords):
                    matched = flow
                    break

        if matched is None:
            return None

        logger.info(
            "tenant=%s flow=%s trigger=%s matched for conversation=%s",
            tenant_id, matched["id"], matched["trigger_type"], message.conversation_id,
        )

        ctx = FlowContext(
            conversation_id=message.conversation_id,
            contact={"external_user_id": message.external_user_id},
            tenant_id=str(tenant_id),
        )
        engine = FlowEngine(conn)
        return await engine.run(
            nodes=matched["nodes"] or [], edges=matched["edges"] or [], ctx=ctx
        )
