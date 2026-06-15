from __future__ import annotations

import logging

from worker.engine.unified import UnifiedMessage
from worker.services.embeddings import EmbeddingService
from worker.services.rag import HIGH_THRESHOLD, LOW_THRESHOLD, RAGService

logger = logging.getLogger(__name__)

_HANDOFF_REPLY_UZ = "Operator sizga tez orada yordam beradi."


class CoreEngine:
    """
    Decision pipeline per ARCHITECTURE.md §Core Engine:
      RAG (step 4) → LLM placeholder (step 4b, Phase 4) → Handoff (step 6)

    score >= HIGH_THRESHOLD  → FREE PATH: direct FAQ answer
    LOW_THRESHOLD <= score < HIGH_THRESHOLD → LLM-grounded answer (Phase 4 placeholder)
    score < LOW_THRESHOLD    → human handoff
    """

    def __init__(self, embedding: EmbeddingService, rag: RAGService) -> None:
        self._emb = embedding
        self._rag = rag

    async def process(
        self,
        msg: UnifiedMessage,
        conn: object,  # asyncpg.Connection — kept untyped to avoid hard import
    ) -> str:
        if not msg.text.strip():
            return ""

        query_emb = self._emb.embed(msg.text)
        matches = await self._rag.search(query_emb, msg.tenant_id, conn)

        if not matches:
            logger.info("tenant=%s text=%r no FAQ matches → handoff", msg.tenant_id, msg.text[:60])
            return _HANDOFF_REPLY_UZ

        top = matches[0]
        logger.info(
            "tenant=%s faq=%s score=%.3f text=%r",
            msg.tenant_id,
            top.faq_id,
            top.score,
            msg.text[:60],
        )

        if top.score >= HIGH_THRESHOLD:
            return top.answer

        if top.score >= LOW_THRESHOLD:
            # Phase 4 will inject the LLM here; for now return the best FAQ directly
            return top.answer

        return _HANDOFF_REPLY_UZ
