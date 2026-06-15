from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from javobai.db.base import Base, TimestampMixin, new_uuid


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # type: ignore[type-arg]
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="tenant")  # type: ignore[name-defined]  # noqa: F821
    channels: Mapped[list["Channel"]] = relationship(back_populates="tenant")  # type: ignore[name-defined]  # noqa: F821
