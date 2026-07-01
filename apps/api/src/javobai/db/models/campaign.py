"""Phase 12 — Campaign model (updated with broadcast metrics)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from javobai.db.base import Base, TimestampMixin, new_uuid


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # broadcast | drip | abandoned_cart | order_update
    campaign_type: Mapped[str] = mapped_column(String(50), nullable=False)
    segment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("segments.id", ondelete="SET NULL")
    )
    channel_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("channels.id", ondelete="SET NULL")
    )
    template: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # draft | scheduled | running | paused | completed | failed
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    stats: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
    # Phase 12 — per-platform delivery metrics
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    read_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicked_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
