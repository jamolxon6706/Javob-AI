from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from javobai.db.base import Base, TimestampMixin, new_uuid


class Segment(Base, TimestampMixin):
    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # JSON filter definition e.g. {"tags": ["vip"], "opt_in": true}
    filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
