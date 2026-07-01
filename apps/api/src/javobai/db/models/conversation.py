from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from javobai.db.base import Base, TimestampMixin, new_uuid


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="SET NULL")
    )
    # open | waiting_operator | resolved | bot_silenced
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False, index=True)
    # For WhatsApp/IG 24h messaging window
    window_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Operator assigned to this convo
    assigned_operator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    # Bot silenced until this time (after operator reply)
    bot_silenced_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Phase 13 — why the conversation was last handed off (analytics grouping):
    # low_confidence | out_of_window | rate_limited | angry_customer
    handoff_reason: Mapped[str | None] = mapped_column(String(50))

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")  # type: ignore[name-defined]  # noqa: F821
