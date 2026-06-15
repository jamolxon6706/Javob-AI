from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from javobai.db.base import Base, TimestampMixin, new_uuid

EMBEDDING_DIM = 1024


class FAQ(Base, TimestampMixin):
    __tablename__ = "faqs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(10), default="uz", nullable=False)
    # Populated async when FAQ is created/updated
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))  # type: ignore[type-arg]
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
