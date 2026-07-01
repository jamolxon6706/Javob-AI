"""Transcribes inbound WhatsApp voice notes so they can flow through the
same RAG/LLM text pipeline as typed messages.

Two providers are supported, selected via settings.STT_PROVIDER:
  - "faster_whisper": local CPU/GPU inference, no per-call cost.
  - "groq_whisper": Groq's hosted Whisper endpoint (OpenAI-compatible).
"""
from __future__ import annotations

import logging

from worker.settings import settings

logger = logging.getLogger(__name__)

_whisper_model = None  # lazy-loaded singleton for faster-whisper


def _get_local_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        # "small" balances accuracy/speed for UZ+RU voice notes; bump to
        # "medium" if quality on Uzbek audio is insufficient.
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper_model


async def transcribe_audio(local_path: str) -> str | None:
    try:
        if settings.STT_PROVIDER == "groq_whisper":
            return await _transcribe_groq(local_path)
        return _transcribe_local(local_path)
    except Exception:  # noqa: BLE001 — transcription failure must not crash the pipeline
        logger.exception("Audio transcription failed for %s", local_path)
        return None


def _transcribe_local(local_path: str) -> str:
    model = _get_local_model()
    segments, _info = model.transcribe(local_path, language=None, task="transcribe")
    return " ".join(segment.text.strip() for segment in segments).strip()


async def _transcribe_groq(local_path: str) -> str:
    import httpx

    async with httpx.AsyncClient(timeout=60) as client:
        with open(local_path, "rb") as f:
            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                files={"file": f},
                data={"model": "whisper-large-v3"},
            )
        resp.raise_for_status()
        return resp.json().get("text", "").strip()
