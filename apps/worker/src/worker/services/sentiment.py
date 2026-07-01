"""
Phase 13 — sentiment tagging (ARCHITECTURE.md §Observability).

Deliberately simple: a keyword match, not a model call. It only needs to
catch clearly angry/frustrated customers so the engine can auto-escalate
them to a human before wasting a RAG/LLM round-trip on a message the bot
was never going to be trusted to answer anyway. False negatives are fine
(the normal pipeline still runs); false positives just mean an early
handoff, which is the safe direction to be wrong in.
"""
from __future__ import annotations

from typing import Literal

Sentiment = Literal["angry", "neutral"]

# Uzbek (Latin) + Russian anger/frustration markers. Lowercased, substring match.
_ANGRY_MARKERS: tuple[str, ...] = (
    # Uzbek
    "jahl", "asabiy", "aqldan", "yomon xizmat", "sharmanda",
    "aldash", "aldayapsiz", "firibgar", "pul qaytar",
    "bekor qil", "shikoyat", "sudga", "yolg'on", "yolgon",
    "eng yomon", "ahmoq", "sotib olmayman", "boshqa hech qachon",
    # Russian
    "ужасно", "отвратительно", "обман", "мошенник", "верните деньги",
    "жалоба", "в суд", "никогда больше", "худший сервис", "идиот",
    "разочарован", "бесит", "достали",
    # Punctuation-based intensity signal (multiple exclamation/caps runs)
    "!!!",
)


def detect_sentiment(text: str) -> Sentiment:
    """Best-effort classification; defaults to 'neutral' when unsure."""
    if not text:
        return "neutral"
    lowered = text.lower()
    for marker in _ANGRY_MARKERS:
        if marker in lowered:
            return "angry"
    return "neutral"
