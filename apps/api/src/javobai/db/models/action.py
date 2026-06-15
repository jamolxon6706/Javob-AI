from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from javobai.db.base import Base, TimestampMixin, new_uuid


class Action(Base, TimestampMixin):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # order_status | book_appointment | collect_lead | webhook
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # JSON schema + endpoint config
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
