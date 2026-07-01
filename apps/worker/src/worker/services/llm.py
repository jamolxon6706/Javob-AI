from __future__ import annotations

import logging

import httpx

from worker.services.rag import RAGMatch

logger = logging.getLogger(__name__)

_NEED_HUMAN = "NEED_HUMAN"

_SYSTEM_PROMPT = (
    "You are a customer-support assistant for a small business in Uzbekistan.\n"
    "Answer ONLY using the FAQ context provided below — never invent facts, prices, "
    "policies, or contact details that are not present in the context.\n"
    "Reply in the same language the customer used (Uzbek or Russian).\n"
    "Keep the answer short and direct, matching the tone of the FAQ answers.\n"
    "If the context does not contain enough information to answer, respond with "
    f"exactly: {_NEED_HUMAN}"
)


def _build_context(candidates: list[RAGMatch]) -> str:
    return "\n\n".join(f"Q: {c.question}\nA: {c.answer}" for c in candidates)


class LLMService:
    """
    Model router for Phase 4 LLM-grounded answers (ARCHITECTURE.md §Core Engine step 4b).

    Primary: Groq (llama-3.3-70b, OpenAI-compatible chat completions) — fast, free-tier.
    Fallback: Gemini, used only if Groq errors out or times out.
    Guardrail: the model is instructed to return the literal token NEED_HUMAN when the
    FAQ context is insufficient to answer; CoreEngine treats `None` as a handoff signal.
    """

    def __init__(
        self,
        groq_api_key: str,
        groq_model: str,
        groq_base_url: str,
        google_api_key: str,
        gemini_model: str,
        timeout: float = 15.0,
    ) -> None:
        self._groq_api_key = groq_api_key
        self._groq_model = groq_model
        self._groq_base_url = groq_base_url
        self._google_api_key = google_api_key
        self._gemini_model = gemini_model
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        """Phase 13 — primary model name recorded on EngineReply for the
        per-answer audit trail. Reports the configured router's primary
        (Groq); the Gemini fallback is an internal retry detail, not
        surfaced separately today — see ARCHITECTURE.md "Decisions"."""
        return self._groq_model

    async def answer_grounded(
        self,
        query: str,
        candidates: list[RAGMatch],
        top_k: int = 3,
    ) -> str | None:
        """Return the grounded answer, or None if guarded/all providers failed (→ handoff)."""
        user_content = (
            f"FAQ context:\n{_build_context(candidates[:top_k])}\n\nCustomer message: {query}"
        )

        text: str | None
        try:
            text = await self._call_groq(user_content)
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            logger.warning("Groq call failed (%s) — falling back to Gemini", exc)
            try:
                text = await self._call_gemini(user_content)
            except Exception as exc2:  # noqa: BLE001 — any provider failure → handoff
                logger.error("Gemini fallback also failed: %s", exc2)
                return None

        text = text.strip()
        if not text or text == _NEED_HUMAN:
            return None
        return text

    async def _call_groq(self, user_content: str) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._groq_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._groq_api_key}"},
                json={
                    "model": self._groq_model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 400,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])

    async def _call_gemini(self, user_content: str) -> str:
        from google import genai  # type: ignore[import-untyped]
        from google.genai import types  # type: ignore[import-untyped]

        client = genai.Client(api_key=self._google_api_key)
        response = await client.aio.models.generate_content(
            model=self._gemini_model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.2,
                max_output_tokens=400,
            ),
        )
        return str(response.text or "")
