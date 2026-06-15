from __future__ import annotations

import logging

import numpy as np

from worker.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


async def embed_faq_job(ctx: dict, faq_id: str) -> None:  # type: ignore[type-arg]
    """Compute and persist the bge-m3 embedding for a single FAQ row."""
    emb: EmbeddingService = ctx["embedding"]
    pool = ctx["db_pool"]

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT question, answer FROM faqs WHERE id = $1",
            faq_id,
        )
        if row is None:
            logger.warning("embed_faq_job: FAQ %s not found — skipping", faq_id)
            return

        text = f"{row['question']} {row['answer']}"
        vector = emb.embed(text)

        await conn.execute(
            "UPDATE faqs SET embedding = $1 WHERE id = $2",
            np.array(vector, dtype=np.float32),
            faq_id,
        )
        logger.info("Embedded FAQ %s (dim=%d)", faq_id, len(vector))


async def probe_embed_job(ctx: dict, text: str) -> list[float]:  # type: ignore[type-arg]
    """Return the bge-m3 embedding for text — used by /internal/embed probe route."""
    emb: EmbeddingService = ctx["embedding"]
    return emb.embed(text)
