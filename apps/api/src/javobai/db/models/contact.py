from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from javobai.db.base import Base, TimestampMixin, new_uuid


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # type: ignore[type-arg]
    opt_in: Mapped[bool] = mapped_column(default=False, nullable=False)
    opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opt_in_source: Mapped[str | None] = mapped_column(String(100))
