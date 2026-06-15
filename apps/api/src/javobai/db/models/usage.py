from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from javobai.db.base import Base, new_uuid


class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("tenant_id", "month", name="uq_usage_tenant_month"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Format: YYYY-MM e.g. "2026-06"
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    replies_count: Mapped[int] = mapped_column(default=0, nullable=False)
    llm_calls_count: Mapped[int] = mapped_column(default=0, nullable=False)
    handoff_count: Mapped[int] = mapped_column(default=0, nullable=False)
