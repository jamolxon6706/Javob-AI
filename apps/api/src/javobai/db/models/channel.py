from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from javobai.db.base import Base, TimestampMixin, new_uuid


class Channel(Base, TimestampMixin):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    # Fernet-encrypted JSON blob containing bot token / access token etc.
    credentials_encrypted: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="channels")  # type: ignore[name-defined]  # noqa: F821
