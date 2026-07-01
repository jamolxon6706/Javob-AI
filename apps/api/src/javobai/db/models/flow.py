from sqlalchemy import Column, String, JSON, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from javobai.db.base import Base
from datetime import datetime


class Flow(Base):
    """Visual flow — stored as JSON graph, executed by FlowEngine."""
    __tablename__ = "flows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    trigger_type = Column(String(50), nullable=False)    # "first_contact" | "keyword" | "action_result" | "schedule"
    trigger_config = Column(JSON, nullable=True)         # e.g. {"keywords": ["salom", "hi"]}
    nodes = Column(JSON, nullable=False, default=list)   # ReactFlow nodes
    edges = Column(JSON, nullable=False, default=list)   # ReactFlow edges
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
