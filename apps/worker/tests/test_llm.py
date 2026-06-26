"""
LLMService unit tests: model router (Groq primary → Gemini fallback) and the
NEED_HUMAN guardrail. All provider calls are mocked — no network access.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from worker.services.llm import LLMService
from worker.services.rag import RAGMatch

_CANDIDATE = RAGMatch(
    faq_id="faq-1",
    question="Narxlar qancha?",
    answer="Bepul tarifimiz bor.",
    language="uz",
    score=0.72,
)


def _make_llm() -> LLMService:
    return LLMService(
        groq_api_key="test-groq-key",
        groq_model="llama-3.3-70b-versatile",
        groq_base_url="https://api.groq.com/openai/v1",
        google_api_key="test-google-key",
        gemini_model="gemini-2.0-flash",
        timeout=5.0,
    )


@pytest.mark.asyncio
async def test_groq_success_returns_text() -> None:
    llm = _make_llm()
    with patch.object(llm, "_call_groq", AsyncMock(return_value="Bepul tarifimiz bor.")):
        reply = await llm.answer_grounded("Narxlar qancha?", [_CANDIDATE])
    assert reply == "Bepul tarifimiz bor."


@pytest.mark.asyncio
async def test_groq_failure_falls_back_to_gemini() -> None:
    llm = _make_llm()
    with (
        patch.object(
            llm, "_call_groq", AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        ),
        patch.object(llm, "_call_gemini", AsyncMock(return_value="Gemini answer")) as gemini,
    ):
        reply = await llm.answer_grounded("Narxlar qancha?", [_CANDIDATE])
    assert reply == "Gemini answer"
    gemini.assert_awaited_once()


@pytest.mark.asyncio
async def test_both_providers_fail_returns_none() -> None:
    llm = _make_llm()
    with (
        patch.object(llm, "_call_groq", AsyncMock(side_effect=httpx.TimeoutException("timeout"))),
        patch.object(llm, "_call_gemini", AsyncMock(side_effect=RuntimeError("quota exceeded"))),
    ):
        reply = await llm.answer_grounded("Narxlar qancha?", [_CANDIDATE])
    assert reply is None


@pytest.mark.asyncio
async def test_need_human_guardrail_returns_none() -> None:
    llm = _make_llm()
    with patch.object(llm, "_call_groq", AsyncMock(return_value="NEED_HUMAN")):
        reply = await llm.answer_grounded("Mutlaqo aloqasiz savol", [_CANDIDATE])
    assert reply is None


@pytest.mark.asyncio
async def test_empty_response_returns_none() -> None:
    llm = _make_llm()
    with patch.object(llm, "_call_groq", AsyncMock(return_value="   ")):
        reply = await llm.answer_grounded("Narxlar qancha?", [_CANDIDATE])
    assert reply is None
