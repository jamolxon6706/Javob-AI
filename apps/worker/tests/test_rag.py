"""
RAG core tests.

Unit tests: CoreEngine routing logic (mocked RAG + embeddings).
Integration test: pgvector retrieval accuracy with seeded FAQs (requires Postgres).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from worker.engine.core import CoreEngine, _HANDOFF_REPLY_UZ
from worker.engine.unified import UnifiedMessage
from worker.services.embeddings import EmbeddingService
from worker.services.llm import LLMService
from worker.services.rag import HIGH_THRESHOLD, LOW_THRESHOLD, RAGMatch, RAGService

from .conftest import POSTGRES_AVAILABLE

# ── Helpers ───────────────────────────────────────────────────────────────────

_TENANT = "tenant-rag-test"


def _make_msg(text: str = "Salom, yordamingiz kerak") -> UnifiedMessage:
    return UnifiedMessage(
        tenant_id=_TENANT,
        platform="telegram",
        channel_id="ch-1",
        kind="dm",
        external_user_id="user-1",
        conversation_id="tg:ch-1:user-1",
        text=text,
        received_at=datetime.now(tz=timezone.utc),
    )


def _mock_embedding(vec: list[float] | None = None) -> EmbeddingService:
    emb = MagicMock(spec=EmbeddingService)
    emb.embed.return_value = vec if vec is not None else [0.1] * 1024
    return emb


def _mock_rag(matches: list[RAGMatch]) -> RAGService:
    rag = MagicMock(spec=RAGService)
    rag.search = AsyncMock(return_value=matches)
    return rag


def _mock_llm(answer: str | None = "LLM grounded answer") -> LLMService:
    llm = MagicMock(spec=LLMService)
    llm.answer_grounded = AsyncMock(return_value=answer)
    return llm


def _faq_match(score: float) -> RAGMatch:
    return RAGMatch(
        faq_id="faq-1",
        question="Narxlar qancha?",
        answer="Bepul tarifimiz bor.",
        language="uz",
        score=score,
    )


# ── CoreEngine unit tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_core_engine_high_score_returns_faq_answer() -> None:
    """score >= HIGH_THRESHOLD → direct FAQ answer (FREE PATH, no LLM call)."""
    llm = _mock_llm()
    engine = CoreEngine(_mock_embedding(), _mock_rag([_faq_match(0.92)]), llm)
    reply = await engine.process(_make_msg(), conn=object())
    assert reply.text == "Bepul tarifimiz bor."
    assert reply.source == "faq"
    assert reply.rag_score == pytest.approx(0.92)
    llm.answer_grounded.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_core_engine_mid_score_returns_llm_answer() -> None:
    """LOW_THRESHOLD <= score < HIGH_THRESHOLD → LLM-grounded answer."""
    llm = _mock_llm(answer="LLM grounded answer")
    engine = CoreEngine(_mock_embedding(), _mock_rag([_faq_match(0.72)]), llm)
    reply = await engine.process(_make_msg(), conn=object())
    assert reply.text == "LLM grounded answer"
    assert reply.source == "llm"
    assert reply.rag_score == pytest.approx(0.72)
    llm.answer_grounded.assert_awaited_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_core_engine_mid_score_llm_guardrail_returns_handoff() -> None:
    """LLM returns None (NEED_HUMAN guardrail or all providers failed) → handoff."""
    engine = CoreEngine(_mock_embedding(), _mock_rag([_faq_match(0.72)]), _mock_llm(answer=None))
    reply = await engine.process(_make_msg(), conn=object())
    assert reply.text == _HANDOFF_REPLY_UZ
    assert reply.source == "handoff"


@pytest.mark.asyncio
async def test_core_engine_low_score_returns_handoff() -> None:
    """score < LOW_THRESHOLD → human handoff message."""
    engine = CoreEngine(_mock_embedding(), _mock_rag([_faq_match(0.50)]), _mock_llm())
    reply = await engine.process(_make_msg(), conn=object())
    assert reply.text == _HANDOFF_REPLY_UZ
    assert reply.source == "handoff"


@pytest.mark.asyncio
async def test_core_engine_no_matches_returns_handoff() -> None:
    """No FAQ matches at all → handoff."""
    engine = CoreEngine(_mock_embedding(), _mock_rag([]), _mock_llm())
    reply = await engine.process(_make_msg(), conn=object())
    assert reply.text == _HANDOFF_REPLY_UZ
    assert reply.source == "handoff"
    assert reply.rag_score is None


@pytest.mark.asyncio
async def test_core_engine_empty_text_returns_empty() -> None:
    """Empty/whitespace message → skip silently."""
    engine = CoreEngine(_mock_embedding(), _mock_rag([]), _mock_llm())
    reply = await engine.process(_make_msg(text="   "), conn=object())
    assert reply.text == ""
    assert reply.source is None


def test_high_threshold_above_low() -> None:
    assert HIGH_THRESHOLD > LOW_THRESHOLD


# ── RAGService unit test (mock asyncpg) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_rag_service_parses_rows() -> None:
    """RAGService.search() should map asyncpg Record-like rows to RAGMatch objects."""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(
        return_value=[
            {"id": "faq-42", "question": "Q?", "answer": "A.", "language": "uz", "score": 0.91},
        ]
    )
    rag = RAGService()
    results = await rag.search([0.0] * 1024, "tenant-x", mock_conn)
    assert len(results) == 1
    assert results[0].faq_id == "faq-42"
    assert results[0].score == pytest.approx(0.91)


# ── Integration: pgvector retrieval accuracy ──────────────────────────────────

_SEED_FAQS = [
    {"question": "Narxlar qancha?", "answer": "Bepul tarifimiz bor.", "language": "uz"},
    {"question": "Qanday to'lov usullari bor?", "answer": "CLICK va Payme.", "language": "uz"},
    {"question": "Qanday bog'lanishim mumkin?", "answer": "+998 71 000 0000", "language": "uz"},
    {"question": "Mahsulot qaerga yetkazib beriladi?", "answer": "Butun O'zbekiston bo'ylab.", "language": "uz"},
    {"question": "Kafolat muddati qancha?", "answer": "1 yil kafolat.", "language": "uz"},
    {"question": "Сколько стоит?", "answer": "У нас есть бесплатный тариф.", "language": "ru"},
    {"question": "Как с вами связаться?", "answer": "+998 71 000 0000", "language": "ru"},
    {"question": "Куда доставляете?", "answer": "По всему Узбекистану.", "language": "ru"},
    {"question": "Какая гарантия?", "answer": "Гарантия 1 год.", "language": "ru"},
    {"question": "Как оплатить?", "answer": "CLICK и Payme.", "language": "ru"},
]


@pytest.fixture(scope="module")
def eval_vectors() -> dict[str, object]:
    """
    Pre-compute 10 unit vectors (one per seed FAQ) and 20 query vectors
    (2 per FAQ: small perturbation simulating UZ + RU paraphrases).

    Uses a fixed numpy seed so results are deterministic in CI.
    """
    rng = np.random.default_rng(42)
    n = len(_SEED_FAQS)
    dim = 1024

    base = rng.standard_normal((n, dim)).astype(np.float32)
    norms = np.linalg.norm(base, axis=1, keepdims=True)
    base = base / norms

    # Two query vectors per FAQ: tiny perturbations, cosine similarity ~0.999
    queries: list[tuple[int, np.ndarray]] = []
    for i in range(n):
        for _ in range(2):
            noise = rng.standard_normal(dim).astype(np.float32) * 0.03
            q = base[i] + noise
            q = q / np.linalg.norm(q)
            queries.append((i, q))

    return {"base": base, "queries": queries}


@pytest.mark.integration
@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="requires PostgreSQL with pgvector")
@pytest.mark.asyncio
async def test_rag_retrieval_accuracy(eval_vectors: dict[str, object]) -> None:
    """
    Seed 10 FAQs with known unit vectors; run 20 paraphrased queries (2 per FAQ);
    assert top-1 retrieval accuracy >= 100%.
    """
    import asyncpg  # type: ignore[import-untyped]
    import pgvector.asyncpg  # type: ignore[import-untyped]

    db_url = os.getenv("DATABASE_URL", "").replace("+asyncpg", "").replace("+aiosqlite", "")
    tenant_id = f"eval-{uuid.uuid4()}"

    base: np.ndarray = eval_vectors["base"]  # type: ignore[assignment]
    queries: list[tuple[int, np.ndarray]] = eval_vectors["queries"]  # type: ignore[assignment]

    async def _init(conn: object) -> None:
        await pgvector.asyncpg.register_vector(conn)  # type: ignore[arg-type]

    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3, init=_init)
    try:
        async with pool.acquire() as conn:
            # Insert seed FAQs
            faq_ids: list[str] = []
            for i, faq in enumerate(_SEED_FAQS):
                faq_id = str(uuid.uuid4())
                faq_ids.append(faq_id)
                await conn.execute(
                    """
                    INSERT INTO faqs (id, tenant_id, question, answer, language, embedding, is_active,
                                      created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, true, NOW(), NOW())
                    """,
                    faq_id,
                    tenant_id,
                    faq["question"],
                    faq["answer"],
                    faq["language"],
                    base[i],
                )

            # Run retrieval accuracy eval
            rag = RAGService()
            hits = 0
            for expected_idx, q_vec in queries:
                matches = await rag.search(q_vec.tolist(), tenant_id, conn, top_k=1)
                if matches and matches[0].faq_id == faq_ids[expected_idx]:
                    hits += 1

            accuracy = hits / len(queries)
            assert accuracy >= 1.0, f"Retrieval accuracy {accuracy:.0%} < 100% — check pgvector setup"

            # Cleanup
            await conn.execute("DELETE FROM faqs WHERE tenant_id = $1", tenant_id)
    finally:
        await pool.close()
