"""
Phase 13 — Analytics, observability & AI eval harness (ARCHITECTURE.md Phase 13).

  GET  /analytics/overview            — reply/handoff rate, volumes, avg latency, angry count
  GET  /analytics/timeseries          — daily inbound/outbound/handoff volume for charts
  GET  /analytics/top-questions       — most frequent inbound questions + "FAQ gaps"
                                         (frequent questions that ended in a handoff)
  GET  /analytics/quality             — latest AI eval harness run + history
  GET  /analytics/eval-cases          — golden test set CRUD
  POST /analytics/eval-cases
  PATCH  /analytics/eval-cases/{id}
  DELETE /analytics/eval-cases/{id}
  POST /analytics/eval-cases/run      — enqueue a harness run (worker.tasks.eval.run_eval_job)

Query patterns favor "fetch the period's rows once, aggregate in Python" over
DB-side date-bucketing (date_trunc etc.) because the test suite runs on
SQLite (see apps/api/tests/conftest.py) and a tenant's message volume is
small enough that this is cheap in production too — see ARCHITECTURE.md
"Decisions".
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.deps import CurrentTenant
from javobai.db.models import Channel, Conversation, EvalCase, EvalResult, EvalRun, Message
from javobai.db.session import get_db
from javobai.analytics.schemas import (
    ChannelVolume,
    EvalCaseIn,
    EvalCaseOut,
    EvalCaseUpdate,
    EvalQualityOut,
    EvalResultOut,
    EvalRunOut,
    EvalRunTriggerOut,
    OverviewOut,
    SourceBreakdown,
    TimeseriesOut,
    TimeseriesPoint,
    TopQuestion,
    TopQuestionsOut,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_OUTBOUND_SOURCES = ("faq", "llm", "action", "flow", "handoff", "operator")


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _normalize_question(text: str) -> str:
    """Cheap clustering key: lowercase, strip punctuation runs, collapse whitespace.

    Not a real semantic clustering (that would mean re-embedding every inbound
    message just to build a dashboard panel) — good enough to group obvious
    repeats/paraphrase-free duplicates for the "top questions" / "FAQ gaps" view.
    """
    lowered = text.strip().lower()
    lowered = re.sub(r"[^\w\s]", "", lowered, flags=re.UNICODE)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


@router.get("/overview", response_model=OverviewOut)
async def get_overview(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=7, ge=1, le=365),
) -> OverviewOut:
    since = _since(days)

    stmt = (
        select(
            Message.direction,
            Message.source,
            Message.sentiment,
            Message.latency_ms,
            Channel.platform,
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(Channel, Conversation.channel_id == Channel.id)
        .where(Message.tenant_id == tenant.id, Message.created_at >= since)
    )
    rows = (await db.execute(stmt)).all()

    inbound = sum(1 for r in rows if r.direction == "inbound")
    outbound = sum(1 for r in rows if r.direction == "outbound")
    angry = sum(1 for r in rows if r.direction == "inbound" and r.sentiment == "angry")

    by_source = SourceBreakdown()
    latencies: list[int] = []
    by_channel: dict[str, dict[str, int]] = defaultdict(lambda: {"inbound": 0, "outbound": 0})

    for r in rows:
        if r.platform:
            by_channel[r.platform][r.direction] = by_channel[r.platform].get(r.direction, 0) + 1
        if r.direction == "outbound" and r.source in _OUTBOUND_SOURCES:
            setattr(by_source, r.source, getattr(by_source, r.source) + 1)
        if r.direction == "outbound" and r.latency_ms is not None:
            latencies.append(r.latency_ms)

    handoff_count = by_source.handoff
    reply_rate = (outbound - handoff_count) / outbound if outbound else 0.0
    handoff_rate = handoff_count / outbound if outbound else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else None

    reason_stmt = select(Conversation.handoff_reason).where(
        Conversation.tenant_id == tenant.id,
        Conversation.handoff_reason.is_not(None),
        Conversation.updated_at >= since,
    )
    reason_rows = (await db.execute(reason_stmt)).all()
    by_handoff_reason: dict[str, int] = dict(Counter(r[0] for r in reason_rows if r[0]))

    conv_count_result = await db.execute(
        select(Conversation.id).where(
            Conversation.tenant_id == tenant.id, Conversation.created_at >= since
        )
    )
    total_conversations = len(conv_count_result.all())

    return OverviewOut(
        days=days,
        total_conversations=total_conversations,
        total_messages=len(rows),
        inbound_messages=inbound,
        outbound_messages=outbound,
        reply_rate=round(reply_rate, 4),
        handoff_rate=round(handoff_rate, 4),
        avg_response_time_ms=round(avg_latency, 1) if avg_latency is not None else None,
        angry_count=angry,
        by_source=by_source,
        by_channel=[
            ChannelVolume(platform=p, inbound=v["inbound"], outbound=v["outbound"])
            for p, v in sorted(by_channel.items())
        ],
        by_handoff_reason=by_handoff_reason,
    )


@router.get("/timeseries", response_model=TimeseriesOut)
async def get_timeseries(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
) -> TimeseriesOut:
    since = _since(days)
    stmt = select(Message.direction, Message.source, Message.created_at).where(
        Message.tenant_id == tenant.id, Message.created_at >= since
    )
    rows = (await db.execute(stmt)).all()

    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"inbound": 0, "outbound": 0, "handoff": 0})
    for r in rows:
        day = r.created_at.date().isoformat()
        buckets[day][r.direction] = buckets[day].get(r.direction, 0) + 1
        if r.direction == "outbound" and r.source == "handoff":
            buckets[day]["handoff"] += 1

    points = [
        TimeseriesPoint(date=day, inbound=v["inbound"], outbound=v["outbound"], handoff=v["handoff"])
        for day, v in sorted(buckets.items())
    ]
    return TimeseriesOut(days=days, points=points)


@router.get("/top-questions", response_model=TopQuestionsOut)
async def get_top_questions(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
) -> TopQuestionsOut:
    since = _since(days)

    content_stmt = (
        select(Message.conversation_id, Message.content)
        .where(
            Message.tenant_id == tenant.id,
            Message.direction == "inbound",
            Message.created_at >= since,
            Message.content.is_not(None),
        )
        .order_by(Message.created_at.desc())
        .limit(5000)
    )
    content_rows = (await db.execute(content_stmt)).all()

    handoff_stmt = select(Message.conversation_id).where(
        Message.tenant_id == tenant.id,
        Message.direction == "outbound",
        Message.source == "handoff",
        Message.created_at >= since,
    )
    handoff_conv_ids = {r[0] for r in (await db.execute(handoff_stmt)).all()}

    all_counter: Counter[str] = Counter()
    gap_counter: Counter[str] = Counter()
    display_text: dict[str, str] = {}

    for conv_id, content in content_rows:
        if not content or not content.strip():
            continue
        key = _normalize_question(content)
        if not key:
            continue
        display_text.setdefault(key, content.strip())
        all_counter[key] += 1
        if conv_id in handoff_conv_ids:
            gap_counter[key] += 1

    top_questions = [
        TopQuestion(text=display_text[k], count=c) for k, c in all_counter.most_common(limit)
    ]
    faq_gaps = [
        TopQuestion(text=display_text[k], count=c) for k, c in gap_counter.most_common(limit)
    ]
    return TopQuestionsOut(top_questions=top_questions, faq_gaps=faq_gaps)


# ── AI eval harness ──────────────────────────────────────────────────────


def _case_to_out(case: EvalCase) -> EvalCaseOut:
    return EvalCaseOut(
        id=case.id,
        question=case.question,
        language=case.language,
        expected_faq_id=case.expected_faq_id,
        expected_answer_contains=case.expected_answer_contains,
        is_active=case.is_active,
    )


def _run_to_out(run: EvalRun) -> EvalRunOut:
    return EvalRunOut(
        id=run.id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        total=run.total,
        passed=run.passed,
        failed=run.failed,
        is_regression=run.is_regression,
    )


@router.get("/eval-cases", response_model=list[EvalCaseOut])
async def list_eval_cases(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[EvalCaseOut]:
    result = await db.execute(
        select(EvalCase).where(EvalCase.tenant_id == tenant.id).order_by(EvalCase.created_at.desc())
    )
    return [_case_to_out(c) for c in result.scalars().all()]


@router.post("/eval-cases", response_model=EvalCaseOut, status_code=status.HTTP_201_CREATED)
async def create_eval_case(
    body: EvalCaseIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EvalCaseOut:
    if body.expected_faq_id is None and body.expected_answer_contains is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide expected_faq_id or expected_answer_contains",
        )
    case = EvalCase(
        tenant_id=tenant.id,
        question=body.question,
        language=body.language,
        expected_faq_id=body.expected_faq_id,
        expected_answer_contains=body.expected_answer_contains,
    )
    db.add(case)
    await db.flush()
    return _case_to_out(case)


@router.patch("/eval-cases/{case_id}", response_model=EvalCaseOut)
async def update_eval_case(
    case_id: str,
    body: EvalCaseUpdate,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EvalCaseOut:
    result = await db.execute(
        select(EvalCase).where(EvalCase.id == case_id, EvalCase.tenant_id == tenant.id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval case not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(case, field, value)
    await db.flush()
    return _case_to_out(case)


@router.delete("/eval-cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_eval_case(
    case_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(EvalCase).where(EvalCase.id == case_id, EvalCase.tenant_id == tenant.id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval case not found")
    await db.delete(case)


@router.post("/eval-cases/run", response_model=EvalRunTriggerOut)
async def trigger_eval_run(
    request: Request,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EvalRunTriggerOut:
    count_result = await db.execute(
        select(EvalCase.id).where(EvalCase.tenant_id == tenant.id, EvalCase.is_active == True)  # noqa: E712
    )
    if not count_result.first():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No active eval cases to run",
        )
    await request.app.state.arq.enqueue_job("run_eval_job", tenant.id)
    return EvalRunTriggerOut(queued=True)


@router.get("/quality", response_model=EvalQualityOut)
async def get_quality(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EvalQualityOut:
    case_count_result = await db.execute(
        select(EvalCase.id).where(EvalCase.tenant_id == tenant.id)
    )
    case_count = len(case_count_result.all())

    history_result = await db.execute(
        select(EvalRun)
        .where(EvalRun.tenant_id == tenant.id)
        .order_by(EvalRun.started_at.desc())
        .limit(20)
    )
    history = history_result.scalars().all()

    latest_run_results: list[EvalResultOut] = []
    if history:
        latest = history[0]
        results_result = await db.execute(
            select(EvalResult, EvalCase.question)
            .join(EvalCase, EvalResult.eval_case_id == EvalCase.id)
            .where(EvalResult.eval_run_id == latest.id)
        )
        for result_row, question in results_result.all():
            latest_run_results.append(
                EvalResultOut(
                    eval_case_id=result_row.eval_case_id,
                    question=question,
                    passed=result_row.passed,
                    actual_source=result_row.actual_source,
                    actual_faq_id=result_row.actual_faq_id,
                    actual_score=result_row.actual_score,
                    actual_answer=result_row.actual_answer,
                )
            )

    return EvalQualityOut(
        case_count=case_count,
        latest_run=_run_to_out(history[0]) if history else None,
        latest_run_results=latest_run_results,
        history=[_run_to_out(r) for r in history],
    )
