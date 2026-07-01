from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from worker.services.eval import REGRESSION_DROP_THRESHOLD, EvalHarness
from worker.services.rag import RAGMatch


def _mock_embedding() -> MagicMock:
    emb = MagicMock()
    emb.embed.return_value = [0.1] * 1024
    return emb


def _mock_rag(matches: list[RAGMatch]) -> MagicMock:
    rag = MagicMock()
    rag.search = AsyncMock(return_value=matches)
    return rag


def _mock_conn(cases: list[dict], previous_run: dict | None = None) -> MagicMock:
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=cases)
    conn.fetchrow = AsyncMock(return_value=previous_run)
    conn.execute = AsyncMock()
    return conn


def _faq_match(faq_id: str, score: float, answer: str = "Bepul tarifimiz bor.") -> RAGMatch:
    return RAGMatch(faq_id=faq_id, question="Narxlar qancha?", answer=answer, language="uz", score=score)


@pytest.mark.asyncio
async def test_eval_harness_no_cases_returns_empty_summary() -> None:
    harness = EvalHarness(_mock_embedding(), _mock_rag([]))
    conn = _mock_conn(cases=[])
    summary = await harness.run("tenant-1", conn)
    assert summary.total == 0
    assert summary.passed == 0
    assert summary.failed == 0
    assert summary.is_regression is False
    conn.execute.assert_awaited()  # still records the (empty) run


@pytest.mark.asyncio
async def test_eval_harness_expected_faq_id_pass() -> None:
    harness = EvalHarness(_mock_embedding(), _mock_rag([_faq_match("faq-1", 0.9)]))
    conn = _mock_conn(cases=[
        {"id": "case-1", "question": "Narxlar qancha?", "expected_faq_id": "faq-1",
         "expected_answer_contains": None},
    ])
    summary = await harness.run("tenant-1", conn)
    assert summary.total == 1
    assert summary.passed == 1
    assert summary.results[0].passed is True
    assert summary.results[0].actual_source == "faq"


@pytest.mark.asyncio
async def test_eval_harness_expected_faq_id_mismatch_fails() -> None:
    harness = EvalHarness(_mock_embedding(), _mock_rag([_faq_match("faq-WRONG", 0.9)]))
    conn = _mock_conn(cases=[
        {"id": "case-1", "question": "Narxlar qancha?", "expected_faq_id": "faq-1",
         "expected_answer_contains": None},
    ])
    summary = await harness.run("tenant-1", conn)
    assert summary.passed == 0
    assert summary.failed == 1


@pytest.mark.asyncio
async def test_eval_harness_no_matches_fails_when_faq_expected() -> None:
    harness = EvalHarness(_mock_embedding(), _mock_rag([]))
    conn = _mock_conn(cases=[
        {"id": "case-1", "question": "Narxlar qancha?", "expected_faq_id": "faq-1",
         "expected_answer_contains": None},
    ])
    summary = await harness.run("tenant-1", conn)
    assert summary.passed == 0
    assert summary.results[0].actual_source == "handoff"


@pytest.mark.asyncio
async def test_eval_harness_expected_answer_contains() -> None:
    harness = EvalHarness(
        _mock_embedding(), _mock_rag([_faq_match("faq-1", 0.9, answer="Yetkazib berish bepul.")])
    )
    conn = _mock_conn(cases=[
        {"id": "case-1", "question": "Yetkazib berish qancha?", "expected_faq_id": None,
         "expected_answer_contains": "bepul"},
    ])
    summary = await harness.run("tenant-1", conn)
    assert summary.passed == 1


@pytest.mark.asyncio
async def test_eval_harness_flags_regression_on_pass_rate_drop() -> None:
    # Previous run: 100% pass rate. Current run: both cases fail → regression.
    harness = EvalHarness(_mock_embedding(), _mock_rag([_faq_match("faq-WRONG", 0.9)]))
    conn = _mock_conn(
        cases=[
            {"id": "case-1", "question": "Q1", "expected_faq_id": "faq-1", "expected_answer_contains": None},
            {"id": "case-2", "question": "Q2", "expected_faq_id": "faq-1", "expected_answer_contains": None},
        ],
        previous_run={"total": 2, "passed": 2},
    )
    summary = await harness.run("tenant-1", conn)
    assert summary.passed == 0
    drop = 1.0 - (summary.passed / summary.total)
    assert drop > REGRESSION_DROP_THRESHOLD
    assert summary.is_regression is True


@pytest.mark.asyncio
async def test_eval_harness_no_regression_when_pass_rate_stable() -> None:
    harness = EvalHarness(_mock_embedding(), _mock_rag([_faq_match("faq-1", 0.9)]))
    conn = _mock_conn(
        cases=[
            {"id": "case-1", "question": "Q1", "expected_faq_id": "faq-1", "expected_answer_contains": None},
        ],
        previous_run={"total": 1, "passed": 1},
    )
    summary = await harness.run("tenant-1", conn)
    assert summary.is_regression is False
