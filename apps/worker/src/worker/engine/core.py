from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Literal, List, Dict, Any, Optional

from worker.engine.unified import UnifiedMessage
from worker.services.embeddings import EmbeddingService
from worker.services.llm import LLMService
from worker.services.rag import HIGH_THRESHOLD, LOW_THRESHOLD, RAGService
from worker.services.action_executor import ActionExecutor
from worker.services.flow_trigger import FlowTrigger

logger = logging.getLogger(__name__)

_HANDOFF_REPLY_UZ = "Operator sizga tez orada yordam beradi."

EngineSource = Literal["faq", "llm", "action", "handoff", "flow"] | None


def _as_json(value: Any, default: Any) -> Any:
    """asyncpg returns json/jsonb columns as raw text unless a codec is
    registered (none is, in worker/main.py's startup()); parse defensively
    so params_schema is always a dict by the time it reaches LLM
    function-calling tool specs."""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        import json

        return json.loads(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class EngineReply:
    text: str
    source: EngineSource
    rag_score: float | None


_EMPTY_REPLY = EngineReply(text="", source=None, rag_score=None)


class CoreEngine:
    """
    Decision pipeline per ARCHITECTURE.md §Core Engine:
      RAG (step 4) → LLM-grounded answer (step 4b) → Agentic action (step 5) → Handoff (step 6)

    score >= HIGH_THRESHOLD  → FREE PATH: direct FAQ answer
    LOW_THRESHOLD <= score < HIGH_THRESHOLD → LLM-grounded answer (model router + guardrails)
    score < LOW_THRESHOLD    → try agentic action; if none matched → human handoff
    """

    def __init__(self, embedding: EmbeddingService, rag: RAGService, llm: LLMService) -> None:
        self._emb = embedding
        self._rag = rag
        self._llm = llm
        self._flow_trigger = FlowTrigger()

    async def _fetch_actions(self, conn, tenant_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Fetch active actions for a tenant from the DB."""
        try:
            rows = await conn.fetch(
                """
                SELECT name, display_name, description, params_schema, action_type, webhook_url, webhook_secret
                FROM tenant_actions
                WHERE tenant_id = $1 AND is_active = true
                """,
                tenant_id,
            )
            actions = []
            for row in rows:
                actions.append(
                    {
                        "name": row["name"],
                        "display_name": row["display_name"],
                        "description": row["description"],
                        "params_schema": _as_json(row["params_schema"], {}),
                        "action_type": row["action_type"],
                        "webhook_url": row["webhook_url"],
                        "webhook_secret": row["webhook_secret"],
                    }
                )
            return actions
        except Exception as e:
            logger.error("Failed to fetch actions for tenant %s: %s", tenant_id, e)
            return []

    def _match_action(self, message: str, actions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Simple keyword-based action matching."""
        msg_lower = message.lower()
        # Define keyword mapping
        keyword_map = {
            "order_status": ["order", "status", "tracking", "where is my"],
            "book_appointment": ["book", "appointment", "schedule", "reserve"],
            "collect_lead": ["lead", "contact", "info", "details", "phone", "name"],
        }
        for action in actions:
            name = action["name"]
            if name in keyword_map:
                for kw in keyword_map[name]:
                    if kw in msg_lower:
                        return action
        return None

    def _extract_parameters(self, message: str, action_name: str) -> Dict[str, Any]:
        """Very basic parameter extraction."""
        params = {}
        if action_name == "order_status":
            # Look for order # or order number
            match = re.search(r"order\s*[#:]?\s*(\d+)", message, re.IGNORECASE)
            if match:
                params["order_id"] = match.group(1)
            else:
                # fallback: any number
                numbers = re.findall(r"\d+", message)
                if numbers:
                    params["order_id"] = numbers[0]
        elif action_name == "book_appointment":
            # extract date/time? Too complex; leave empty
            pass
        elif action_name == "collect_lead":
            # extract name and phone using simple regex
            # name: capture capitalized words? We'll just leave empty.
            pass
        return params

    async def process(
        self,
        msg: UnifiedMessage,
        conn: object,  # asyncpg.Connection — kept untyped to avoid hard import
    ) -> EngineReply:
        if not msg.text.strip() and not msg.media:
            # Even an empty-text message (e.g. a bare attachment) should
            # still be allowed to trigger a first_contact flow, so only
            # bail out here for the genuinely-empty case.
            return _EMPTY_REPLY

        # Flow trigger (Phase 11) — runs BEFORE RAG so a matched
        # first_contact/keyword flow short-circuits the FAQ/LLM/action
        # pipeline entirely, per ARCHITECTURE.md §Core Engine.
        try:
            flow_messages = await self._flow_trigger.match_and_run(msg, conn)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("tenant=%s flow trigger failed: %s", msg.tenant_id, exc)
            flow_messages = None
        if flow_messages:
            # NOTE: OutboundDispatcher.send() only supports a single reply
            # string per inbound message today, so a multi-message flow is
            # joined into one outbound message. Sending each flow message
            # as a separate outbound message would require extending
            # OutboundDispatcher to accept a list — left as a follow-up.
            return EngineReply(
                text="\n\n".join(m for m in flow_messages if m),
                source="flow",
                rag_score=None,
            )

        if not msg.text.strip():
            return _EMPTY_REPLY

        query_emb = self._emb.embed(msg.text)
        matches = await self._rag.search(query_emb, msg.tenant_id, conn)

        if not matches:
            logger.info("tenant=%s text=%r no FAQ matches → handoff", msg.tenant_id, msg.text[:60])
            return EngineReply(text=_HANDOFF_REPLY_UZ, source="handoff", rag_score=None)

        top = matches[0]
        logger.info(
            "tenant=%s faq=%s score=%.3f text=%r",
            msg.tenant_id,
            top.faq_id,
            top.score,
            msg.text[:60],
        )

        if top.score >= HIGH_THRESHOLD:
            return EngineReply(text=top.answer, source="faq", rag_score=top.score)

        if top.score >= LOW_THRESHOLD:
            answer = await self._llm.answer_grounded(msg.text, matches)
            if answer is None:
                logger.info("tenant=%s LLM guardrail/failure → handoff", msg.tenant_id)
                return EngineReply(text=_HANDOFF_REPLY_UZ, source="handoff", rag_score=top.score)
            return EngineReply(text=answer, source="llm", rag_score=top.score)

        # Low confidence: try agentic action
        # BUG FIX: uuid.UUID(msg.tenant_id) used to be called unguarded —
        # if tenant_id is ever not a well-formed UUID (bad data, a test
        # fixture, a future non-UUID tenant id scheme), this raised
        # ValueError and crashed the entire ARQ job instead of degrading
        # gracefully to handoff like every other failure path here does.
        try:
            tenant_id_uuid = uuid.UUID(msg.tenant_id)
        except ValueError:
            logger.error("tenant=%s is not a valid UUID — skipping action lookup", msg.tenant_id)
            return EngineReply(text=_HANDOFF_REPLY_UZ, source="handoff", rag_score=top.score)
        actions = await self._fetch_actions(conn, tenant_id_uuid)
        if actions:
            action = self._match_action(msg.text, actions)
            if action:
                logger.info(
                    "tenant=%s action matched: %s",
                    msg.tenant_id,
                    action["name"],
                )
                params = self._extract_parameters(msg.text, action["name"])
                executor = ActionExecutor()
                try:
                    result = await executor.execute(action, params)
                except Exception as e:
                    logger.error("Action execution failed: %s", e)
                    result = {"status": "error", "error": str(e), "outputs": {}}
                if result.get("status") == "success":
                    # Try to get a user-friendly message from outputs
                    output_msg = result.get("outputs", {}).get("message")
                    if not output_msg:
                        # fallback: construct from outputs
                        output_msg = str(result.get("outputs", ""))
                    if not output_msg:
                        output_msg = "Amaliyot bajarildi."
                    return EngineReply(text=output_msg, source="action", rag_score=top.score)
                else:
                    # action failed, fallback to handoff
                    logger.info(
                        "tenant=%s action %s failed: %s",
                        msg.tenant_id,
                        action["name"],
                        result.get("error"),
                    )
        # If no action matched or action failed, handoff
        return EngineReply(text=_HANDOFF_REPLY_UZ, source="handoff", rag_score=top.score)
