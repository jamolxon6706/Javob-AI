from __future__ import annotations

from worker.services.sentiment import detect_sentiment


def test_detect_sentiment_neutral_by_default() -> None:
    assert detect_sentiment("Ish vaqtingiz qachon?") == "neutral"


def test_detect_sentiment_empty_text() -> None:
    assert detect_sentiment("") == "neutral"


def test_detect_sentiment_angry_uzbek() -> None:
    assert detect_sentiment("Bu eng yomon xizmat, pul qaytaring!") == "angry"


def test_detect_sentiment_angry_russian() -> None:
    assert detect_sentiment("Это ужасно, верните деньги немедленно") == "angry"


def test_detect_sentiment_is_case_insensitive() -> None:
    assert detect_sentiment("МОШЕННИК! ОБМАН!") == "angry"


def test_detect_sentiment_intensity_punctuation() -> None:
    assert detect_sentiment("Qachon javob berasiz!!!") == "angry"
