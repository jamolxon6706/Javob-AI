from pydantic import BaseModel, Field
from typing import Any, Optional
from uuid import UUID
from datetime import datetime


class FlowCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    trigger_type: str = Field(..., pattern=r"^(first_contact|keyword|action_result|schedule)$")
    trigger_config: Optional[dict[str, Any]] = None
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []


class FlowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict[str, Any]] = None
    nodes: Optional[list[dict[str, Any]]] = None
    edges: Optional[list[dict[str, Any]]] = None
    is_active: Optional[bool] = None


class FlowRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    trigger_type: str
    trigger_config: Optional[dict[str, Any]]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
