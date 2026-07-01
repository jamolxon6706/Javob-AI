from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SourceBreakdown(BaseModel):
    faq: int = 0
    llm: int = 0
    action: int = 0
    flow: int = 0
    handoff: int = 0
    operator: int = 0


class ChannelVolume(BaseModel):
    platform: str
    inbound: int
    outbound: int


class OverviewOut(BaseModel):
    days: int
    total_conversations: int
    total_messages: int
    inbound_messages: int
    outbound_messages: int
    reply_rate: float  # (outbound - handoff) / outbound, 0..1
    handoff_rate: float  # handoff / outbound, 0..1
    avg_response_time_ms: float | None
    angry_count: int
    by_source: SourceBreakdown
    by_channel: list[ChannelVolume]
    by_handoff_reason: dict[str, int]


class TimeseriesPoint(BaseModel):
    date: str  # YYYY-MM-DD
    inbound: int
    outbound: int
    handoff: int


class TimeseriesOut(BaseModel):
    days: int
    points: list[TimeseriesPoint]


class TopQuestion(BaseModel):
    text: str
    count: int


class TopQuestionsOut(BaseModel):
    top_questions: list[TopQuestion]
    faq_gaps: list[TopQuestion]  # frequent questions that ended in a handoff


# ── AI eval harness ──────────────────────────────────────────────────────


class EvalCaseIn(BaseModel):
    question: str
    language: str = "uz"
    expected_faq_id: str | None = None
    expected_answer_contains: str | None = None


class EvalCaseUpdate(BaseModel):
    question: str | None = None
    language: str | None = None
    expected_faq_id: str | None = None
    expected_answer_contains: str | None = None
    is_active: bool | None = None


class EvalCaseOut(BaseModel):
    id: str
    question: str
    language: str
    expected_faq_id: str | None
    expected_answer_contains: str | None
    is_active: bool


class EvalResultOut(BaseModel):
    eval_case_id: str
    question: str
    passed: bool
    actual_source: str | None
    actual_faq_id: str | None
    actual_score: float | None
    actual_answer: str | None


class EvalRunOut(BaseModel):
    id: str
    started_at: datetime
    finished_at: datetime | None
    total: int
    passed: int
    failed: int
    is_regression: bool


class EvalQualityOut(BaseModel):
    case_count: int
    latest_run: EvalRunOut | None
    latest_run_results: list[EvalResultOut]
    history: list[EvalRunOut]


class EvalRunTriggerOut(BaseModel):
    queued: bool
