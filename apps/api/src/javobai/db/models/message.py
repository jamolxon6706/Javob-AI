from sqlalchemy import ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from javobai.db.base import Base, TimestampMixin, new_uuid


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # inbound | outbound
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    media: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # type: ignore[type-arg]
    # Platform-side message id for dedup
    platform_msg_id: Mapped[str | None] = mapped_column(String(255), index=True)
    # rule | faq | llm | action | flow | operator | handoff
    source: Mapped[str | None] = mapped_column(String(50))
    # RAG score if source==faq or llm
    rag_score: Mapped[float | None] = mapped_column()
    # Phase 13 — per-answer audit trail (observability).
    model: Mapped[str | None] = mapped_column(String(100))
    latency_ms: Mapped[int | None] = mapped_column()
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0, nullable=False)
    # angry | neutral | positive — tagged on inbound messages only.
    sentiment: Mapped[str | None] = mapped_column(String(20))

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")  # type: ignore[name-defined]  # noqa: F821
