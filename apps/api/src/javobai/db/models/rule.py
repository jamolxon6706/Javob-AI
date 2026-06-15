from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from javobai.db.base import Base, TimestampMixin, new_uuid


class Rule(Base, TimestampMixin):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # keyword | out_of_hours | stop_word | comment_to_dm | first_contact
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
    # reply | handoff | assign | silence
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action_value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    priority: Mapped[int] = mapped_column(default=0, nullable=False)
