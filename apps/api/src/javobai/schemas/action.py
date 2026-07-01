from pydantic import BaseModel, Field
from typing import Any, Optional
from uuid import UUID
from datetime import datetime


class ParamsSchema(BaseModel):
    type: str = "object"
    properties: dict[str, Any]
    required: list[str] = []


class TenantActionCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z_]+$")
    display_name: str = Field(..., max_length=200)
    description: str
    params_schema: ParamsSchema
    action_type: str = Field(..., pattern=r"^(webhook|builtin)$")
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None


class TenantActionUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    is_active: Optional[bool] = None


class TenantActionRead(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: str
    params_schema: dict[str, Any]
    action_type: str
    webhook_url: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ActionLogRead(BaseModel):
    id: UUID
    action_name: str
    inputs: Optional[dict[str, Any]]
    outputs: Optional[dict[str, Any]]
    status: str
    error_message: Optional[str]
    duration_ms: Optional[str]
    called_at: datetime

    class Config:
        from_attributes = True
