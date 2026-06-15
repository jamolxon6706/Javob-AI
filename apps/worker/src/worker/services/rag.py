from __future__ import annotations

from dataclasses import dataclass

import numpy as np

HIGH_THRESHOLD = 0.85
LOW_THRESHOLD = 0.65


@dataclass(frozen=True)
class RAGMatch:
    faq_id: str
    question: str
    answer: str
    language: str
    score: float


class RAGService:
    """pgvector cosine-similarity FAQ retrieval via asyncpg."""

    async def search(
        self,
        query_embedding: list[float],
        tenant_id: str,
        conn: object,  # asyncpg.Connection — untyped to avoid hard import
        top_k: int = 5,
    ) -> list[RAGMatch]:
        rows = await conn.fetch(  # type: ignore[attr-defined]
            """
            SELECT id, question, answer, language,
                   1 - (embedding <=> $1) AS score
            FROM faqs
            WHERE tenant_id = $2
              AND is_active = true
              AND embedding IS NOT NULL
            ORDER BY embedding <=> $1
            LIMIT $3
            """,
            np.array(query_embedding, dtype=np.float32),
            tenant_id,
            top_k,
        )
        return [
            RAGMatch(
                faq_id=str(row["id"]),
                question=str(row["question"]),
                answer=str(row["answer"]),
                language=str(row["language"]),
                score=float(row["score"]),
            )
            for row in rows
        ]
