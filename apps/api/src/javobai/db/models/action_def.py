from sqlalchemy import Column, String, JSON, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from javobai.db.base import Base
from datetime import datetime


class TenantAction(Base):
    """Registered tool/action per tenant, exposed to LLM via function-calling."""
    __tablename__ = "tenant_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)           # e.g. "order_status"
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)           # shown to LLM
    params_schema = Column(JSON, nullable=False)         # JSON Schema for params
    action_type = Column(String(50), nullable=False)     # "webhook" | "builtin"
    webhook_url = Column(String(500), nullable=True)     # for webhook type
    webhook_secret = Column(String(255), nullable=True)  # encrypted
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActionLog(Base):
    """Audit log for every action call."""
    __tablename__ = "action_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    action_id = Column(UUID(as_uuid=True), ForeignKey("tenant_actions.id"), nullable=True)
    conversation_id = Column(UUID(as_uuid=True), nullable=True)
    action_name = Column(String(100), nullable=False)
    inputs = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False)          # "success" | "error" | "timeout"
    error_message = Column(Text, nullable=True)
    duration_ms = Column(String(20), nullable=True)
    called_at = Column(DateTime, default=datetime.utcnow)
