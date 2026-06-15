from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from javobai.db.base import Base, TimestampMixin, new_uuid


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # click | payme
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[int] = mapped_column(nullable=False)  # in tiyin (UZS * 100)
    currency: Mapped[str] = mapped_column(String(10), default="UZS", nullable=False)
    # pending | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    plan: Mapped[str | None] = mapped_column(String(50))
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
