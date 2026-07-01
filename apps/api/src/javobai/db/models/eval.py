from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from javobai.db.base import Base, TimestampMixin, new_uuid


class EvalCase(Base, TimestampMixin):
    """A single golden test-set entry: 'this question should retrieve this FAQ'."""

    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="uz", nullable=False)
    # If set: retrieval must return this FAQ as the top match to pass.
    expected_faq_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("faqs.id", ondelete="SET NULL")
    )
    # If set (and expected_faq_id is not): the returned answer must contain
    # this substring (case-insensitive) to pass — for LLM-path cases.
    expected_answer_contains: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EvalRun(Base):
    """One execution of the AI eval harness for a tenant."""

    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total: Mapped[int] = mapped_column(default=0, nullable=False)
    passed: Mapped[int] = mapped_column(default=0, nullable=False)
    failed: Mapped[int] = mapped_column(default=0, nullable=False)
    # True when pass-rate dropped more than the configured threshold vs. the
    # previous run — a CI-style regression flag, per ARCHITECTURE.md Phase 13.
    is_regression: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvalResult(Base):
    """Per-case outcome within one EvalRun."""

    __tablename__ = "eval_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    eval_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    eval_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("eval_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_source: Mapped[str | None] = mapped_column(String(50))
    actual_faq_id: Mapped[str | None] = mapped_column(String(36))
    actual_score: Mapped[float | None] = mapped_column(Float)
    actual_answer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
