"""FlowEngine: executes a JSON flow graph node by node.

Nodes: trigger, message, condition, action, wait, end
Edges: source -> target (with optional condition label)

BUG FIX (Band 8): this file used to reference `Flow` and `TenantAction`
without importing them (NameError at call time) and used a SQLAlchemy
`AsyncSession` (self.db) for queries, while every other part of the worker
(CoreEngine, conversation.py, dispatcher.py) uses a raw asyncpg connection.
Mixing the two DB layers inside one ARQ job is not possible — there is no
SQLAlchemy AsyncSession available in the worker's asyncpg-based context.
Rewritten to take an asyncpg connection and plain dict/row data, matching
CoreEngine._fetch_actions' pattern.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional
from uuid import UUID

from worker.services.action_executor import ActionExecutor

logger = logging.getLogger(__name__)

NodeId = str

# Hard ceiling on nodes executed per flow run — prevents infinite loops from
# a malformed graph (e.g. a condition cycle) from hanging a worker job.
_MAX_STEPS = 20


def _as_json(value: Any, default: Any) -> Any:
    """asyncpg returns json/jsonb columns as raw text unless a codec is
    registered (none is, in worker/main.py's startup())."""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class FlowContext:
    def __init__(
        self,
        conversation_id: str,
        contact: dict[str, Any],
        tenant_id: str,
    ):
        self.conversation_id = conversation_id
        self.contact = contact
        self.tenant_id = tenant_id
        self.variables: dict[str, Any] = {}
        self.sent_messages: list[str] = []


class FlowEngine:
    """Executes a flow's node graph against an asyncpg connection."""

    def __init__(self, conn: object) -> None:  # asyncpg.Connection
        self._conn = conn

    @staticmethod
    def _node_map(nodes: list[dict]) -> dict[NodeId, dict]:
        return {n["id"]: n for n in nodes}

    @staticmethod
    def _edge_map(edges: list[dict]) -> dict[NodeId, list[dict]]:
        out: dict[NodeId, list[dict]] = {}
        for e in edges:
            out.setdefault(e["source"], []).append(e)
        return out

    @staticmethod
    def _find_start(node_map: dict[NodeId, dict]) -> Optional[str]:
        for nid, node in node_map.items():
            if node.get("type") == "trigger":
                return nid
        return None

    async def run(
        self,
        *,
        nodes: list[dict],
        edges: list[dict],
        ctx: FlowContext,
    ) -> list[str]:
        """Execute flow. Returns list of messages to send to the user."""
        node_map = self._node_map(nodes)
        edge_map = self._edge_map(edges)
        current_id = self._find_start(node_map)

        steps = 0
        while current_id and steps < _MAX_STEPS:
            node = node_map.get(current_id)
            if not node:
                break

            next_id = await self._execute_node(node, edge_map, ctx)
            current_id = next_id
            steps += 1

        return ctx.sent_messages

    async def _execute_node(
        self,
        node: dict,
        edge_map: dict[NodeId, list[dict]],
        ctx: FlowContext,
    ) -> Optional[NodeId]:
        ntype = node.get("type")
        data = node.get("data", {})
        nid = node["id"]

        if ntype == "trigger":
            return self._next(nid, edge_map)

        elif ntype == "message":
            text = self._interpolate(data.get("text", ""), ctx)
            ctx.sent_messages.append(text)
            return self._next(nid, edge_map)

        elif ntype == "condition":
            variable = ctx.variables.get(data.get("variable", ""))
            operator = data.get("operator", "eq")
            value = data.get("value")

            result = self._evaluate_condition(variable, operator, value)
            label = "true" if result else "false"
            return self._next(nid, edge_map, label=label)

        elif ntype == "action":
            action_name = data.get("action_name")
            params = {
                k: self._interpolate(v, ctx) if isinstance(v, str) else v
                for k, v in data.get("params", {}).items()
            }
            result = await self._run_action(action_name, params, ctx)
            ctx.variables[f"{action_name}_result"] = result
            return self._next(nid, edge_map)

        elif ntype == "wait":
            delay_seconds = data.get("delay_seconds", 0)
            if delay_seconds and delay_seconds < 10:
                await asyncio.sleep(delay_seconds)
            return self._next(nid, edge_map)

        elif ntype == "end":
            return None

        return self._next(nid, edge_map)

    def _next(
        self,
        node_id: NodeId,
        edge_map: dict[NodeId, list[dict]],
        label: Optional[str] = None,
    ) -> Optional[NodeId]:
        edges = edge_map.get(node_id, [])
        if not edges:
            return None
        if label:
            for e in edges:
                if e.get("label") == label:
                    return e["target"]
            return None
        return edges[0]["target"]

    def _interpolate(self, text: str, ctx: FlowContext) -> str:
        """Replace {{variable}} placeholders."""
        for k, v in ctx.variables.items():
            text = text.replace(f"{{{{{k}}}}}", str(v))
        for k, v in ctx.contact.items():
            text = text.replace(f"{{{{contact.{k}}}}}", str(v))
        return text

    @staticmethod
    def _evaluate_condition(variable: Any, operator: str, value: Any) -> bool:
        if operator == "eq":
            return str(variable) == str(value)
        elif operator == "neq":
            return str(variable) != str(value)
        elif operator == "contains":
            return str(value).lower() in str(variable).lower()
        elif operator == "gt":
            return float(variable or 0) > float(value or 0)
        elif operator == "lt":
            return float(variable or 0) < float(value or 0)
        elif operator == "exists":
            return variable is not None
        return False

    async def _run_action(
        self, action_name: str, params: dict, ctx: FlowContext
    ) -> dict[str, Any]:
        row = await self._conn.fetchrow(  # type: ignore[attr-defined]
            """
            SELECT name, display_name, description, params_schema, action_type,
                   webhook_url, webhook_secret
            FROM tenant_actions
            WHERE tenant_id = $1 AND name = $2 AND is_active = true
            """,
            UUID(str(ctx.tenant_id)),
            action_name,
        )
        if row is None:
            return {"error": f"Action '{action_name}' not found"}

        action = {
            "name": row["name"],
            "display_name": row["display_name"],
            "description": row["description"],
            "params_schema": _as_json(row["params_schema"], {}),
            "action_type": row["action_type"],
            "webhook_url": row["webhook_url"],
            "webhook_secret": row["webhook_secret"],
        }
        executor = ActionExecutor()
        try:
            return await executor.execute(action, params)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Flow action %s failed: %s", action_name, exc)
            return {"error": str(exc)}
