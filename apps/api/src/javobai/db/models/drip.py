"""Phase 12 — drip sequence models."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from javobai.db.base import Base, TimestampMixin, new_uuid


class DripSequence(Base, TimestampMixin):
    __tablename__ = "drip_sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # first_contact | opt_in | tag_added | webhook
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class DripStep(Base):
    __tablename__ = "drip_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    sequence_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("drip_sequences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    # message | condition | wait
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
    wait_minutes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DripEnrollment(Base):
    __tablename__ = "drip_enrollments"
    __table_args__ = (UniqueConstraint("sequence_id", "contact_id", name="uq_drip_enrollment"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    sequence_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("drip_sequences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # active | paused | completed | unsubscribed
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    next_send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
