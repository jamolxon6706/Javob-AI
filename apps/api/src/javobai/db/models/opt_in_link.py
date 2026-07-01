"""Phase 12 — opt-in entry points (click-to-chat / QR links)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from javobai.db.base import Base, new_uuid


class OptInLink(Base):
    __tablename__ = "opt_in_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # whatsapp | telegram | instagram
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("channels.id", ondelete="CASCADE")
    )
    welcome_message: Mapped[str | None] = mapped_column(Text)
    drip_sequence_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("drip_sequences.id", ondelete="SET NULL")
    )
    scan_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
