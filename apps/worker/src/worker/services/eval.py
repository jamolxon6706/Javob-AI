"""
Phase 13 — AI eval harness (ARCHITECTURE.md §Observability).

"AI eval harness: a golden test set per tenant; CI job that detects
regressions in retrieval/answer quality."

Each EvalCase is a (question, expected outcome) pair maintained by the
tenant in the dashboard (Faza 13 API). Running the harness re-embeds each
question and runs it through the same RAGService used in production, so a
regression here means production retrieval degraded too — not a
harness-only artifact.

Scope, deliberately: this checks *retrieval* (which FAQ, or "not found"),
not full LLM generation — grounded-answer quality depends on the LLM
provider's live behavior, which is out of this repo's control to pin down
in a repeatable test. `expected_answer_contains` cases still exercise the
low/high-threshold routing decision even though the harness doesn't call
the LLM to keep runs fast and free of API cost.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from worker.services.embeddings import EmbeddingService
from worker.services.rag import HIGH_THRESHOLD, LOW_THRESHOLD, RAGService

logger = logging.getLogger(__name__)

# A run is flagged as a regression when its pass-rate drops by more than this
# many percentage points versus the immediately preceding run for the tenant.
REGRESSION_DROP_THRESHOLD = 0.10


@dataclass(frozen=True)
class EvalCaseRow:
    id: str
    question: str
    expected_faq_id: str | None
    expected_answer_contains: str | None


@dataclass(frozen=True)
class EvalCaseResult:
    eval_case_id: str
    passed: bool
    actual_source: str  # faq | llm | handoff
    actual_faq_id: str | None
    actual_score: float | None
    actual_answer: str | None


@dataclass(frozen=True)
class EvalRunSummary:
    id: str
    total: int
    passed: int
    failed: int
    is_regression: bool
    results: list[EvalCaseResult]


class EvalHarness:
    """Runs a tenant's golden test set through retrieval and records the outcome."""

    def __init__(self, embedding: EmbeddingService, rag: RAGService) -> None:
        self._emb = embedding
        self._rag = rag

    async def _fetch_cases(self, conn: object, tenant_id: str) -> list[EvalCaseRow]:
        rows = await conn.fetch(  # type: ignore[attr-defined]
            """
            SELECT id, question, expected_faq_id, expected_answer_contains
            FROM eval_cases
            WHERE tenant_id = $1 AND is_active = true
            ORDER BY created_at
            """,
            tenant_id,
        )
        return [
            EvalCaseRow(
                id=str(r["id"]),
                question=str(r["question"]),
                expected_faq_id=str(r["expected_faq_id"]) if r["expected_faq_id"] else None,
                expected_answer_contains=r["expected_answer_contains"],
            )
            for r in rows
        ]

    async def _run_case(self, case: EvalCaseRow, tenant_id: str, conn: object) -> EvalCaseResult:
        query_emb = self._emb.embed(case.question)
        matches = await self._rag.search(query_emb, tenant_id, conn)

        if not matches:
            passed = case.expected_faq_id is None and case.expected_answer_contains is None
            return EvalCaseResult(
                eval_case_id=case.id, passed=passed, actual_source="handoff",
                actual_faq_id=None, actual_score=None, actual_answer=None,
            )

        top = matches[0]

        if case.expected_faq_id is not None:
            passed = top.faq_id == case.expected_faq_id and top.score >= LOW_THRESHOLD
            source = "faq" if top.score >= HIGH_THRESHOLD else (
                "llm" if top.score >= LOW_THRESHOLD else "handoff"
            )
            return EvalCaseResult(
                eval_case_id=case.id, passed=passed, actual_source=source,
                actual_faq_id=top.faq_id, actual_score=top.score, actual_answer=top.answer,
            )

        if case.expected_answer_contains is not None:
            needle = case.expected_answer_contains.lower()
            passed = top.score >= LOW_THRESHOLD and needle in top.answer.lower()
            source = "faq" if top.score >= HIGH_THRESHOLD else (
                "llm" if top.score >= LOW_THRESHOLD else "handoff"
            )
            return EvalCaseResult(
                eval_case_id=case.id, passed=passed, actual_source=source,
                actual_faq_id=top.faq_id, actual_score=top.score, actual_answer=top.answer,
            )

        # No expectation configured — just record what happened, don't fail it.
        return EvalCaseResult(
            eval_case_id=case.id, passed=True, actual_source="faq" if top.score >= HIGH_THRESHOLD else "llm",
            actual_faq_id=top.faq_id, actual_score=top.score, actual_answer=top.answer,
        )

    async def _previous_pass_rate(self, conn: object, tenant_id: str) -> float | None:
        row = await conn.fetchrow(  # type: ignore[attr-defined]
            """
            SELECT total, passed FROM eval_runs
            WHERE tenant_id = $1 AND finished_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT 1
            """,
            tenant_id,
        )
        if row is None or not row["total"]:
            return None
        return float(row["passed"]) / float(row["total"])

    async def run(self, tenant_id: str, conn: object) -> EvalRunSummary:
        cases = await self._fetch_cases(conn, tenant_id)
        started_at = datetime.now(timezone.utc)
        previous_pass_rate = await self._previous_pass_rate(conn, tenant_id)

        results = [await self._run_case(c, tenant_id, conn) for c in cases]
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        is_regression = False
        if total > 0 and previous_pass_rate is not None:
            current_pass_rate = passed / total
            is_regression = (previous_pass_rate - current_pass_rate) > REGRESSION_DROP_THRESHOLD

        run_id = str(uuid.uuid4())
        finished_at = datetime.now(timezone.utc)
        await conn.execute(  # type: ignore[attr-defined]
            """
            INSERT INTO eval_runs
                (id, tenant_id, started_at, finished_at, total, passed, failed, is_regression, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            """,
            run_id, tenant_id, started_at, finished_at, total, passed, failed, is_regression,
        )
        for r in results:
            await conn.execute(  # type: ignore[attr-defined]
                """
                INSERT INTO eval_results
                    (id, eval_run_id, eval_case_id, passed, actual_source, actual_faq_id,
                     actual_score, actual_answer, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                """,
                str(uuid.uuid4()), run_id, r.eval_case_id, r.passed, r.actual_source,
                r.actual_faq_id, r.actual_score, r.actual_answer,
            )

        if is_regression:
            logger.warning(
                "tenant=%s eval run=%s REGRESSION detected: pass_rate %.2f -> %.2f",
                tenant_id, run_id, previous_pass_rate, passed / total if total else 0.0,
            )
        else:
            logger.info(
                "tenant=%s eval run=%s passed=%d/%d", tenant_id, run_id, passed, total,
            )

        return EvalRunSummary(
            id=run_id, total=total, passed=passed, failed=failed,
            is_regression=is_regression, results=results,
        )
