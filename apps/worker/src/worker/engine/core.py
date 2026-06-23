from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from worker.engine.unified import UnifiedMessage
from worker.services.embeddings import EmbeddingService
from worker.services.llm import LLMService
from worker.services.rag import HIGH_THRESHOLD, LOW_THRESHOLD, RAGService

logger = logging.getLogger(__name__)

_HANDOFF_REPLY_UZ = "Operator sizga tez orada yordam beradi."

EngineSource = Literal["faq", "llm", "handoff"] | None


@dataclass(frozen=True)
class EngineReply:
    text: str
    source: EngineSource
    rag_score: float | None


_EMPTY_REPLY = EngineReply(text="", source=None, rag_score=None)


class CoreEngine:
    """
    Decision pipeline per ARCHITECTURE.md §Core Engine:
      RAG (step 4) → LLM-grounded answer (step 4b) → Handoff (step 6)

    score >= HIGH_THRESHOLD  → FREE PATH: direct FAQ answer
    LOW_THRESHOLD <= score < HIGH_THRESHOLD → LLM-grounded answer (model router + guardrails)
    score < LOW_THRESHOLD    → human handoff
    """

    def __init__(self, embedding: EmbeddingService, rag: RAGService, llm: LLMService) -> None:
        self._emb = embedding
        self._rag = rag
        self._llm = llm

    async def process(
        self,
        msg: UnifiedMessage,
        conn: object,  # asyncpg.Connection — kept untyped to avoid hard import
    ) -> EngineReply:
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

        return EngineReply(text=_HANDOFF_REPLY_UZ, source="handoff", rag_score=top.score)
