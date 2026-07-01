"""Phase 12 — Growth layer Pydantic schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ─── Contacts ────────────────────────────────────────────────────────────────

class ContactOut(BaseModel):
    id: str
    tenant_id: str
    external_user_id: str
    platform: str
    name: str | None
    phone: str | None
    email: str | None
    tags: list[str]
    opt_in: bool
    opt_in_at: datetime | None
    opt_in_source: str | None
    opt_out_at: datetime | None
    notes: str | None
    custom_fields: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class ContactUpdateIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    custom_fields: dict | None = None


class ContactOptInIn(BaseModel):
    opt_in: bool
    source: str | None = None


# ─── Segments ─────────────────────────────────────────────────────────────────

class SegmentIn(BaseModel):
    name: str
    filters: dict = Field(default_factory=dict)


class SegmentOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    filters: dict
    created_at: datetime

    class Config:
        from_attributes = True


class SegmentPreviewOut(BaseModel):
    count: int
    sample: list[ContactOut]


# ─── Campaigns ────────────────────────────────────────────────────────────────

class CampaignIn(BaseModel):
    name: str
    campaign_type: str = "broadcast"  # broadcast | drip | abandoned_cart | order_update
    segment_id: str | None = None
    template: dict = Field(default_factory=dict)
    scheduled_at: datetime | None = None


class CampaignOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    campaign_type: str
    segment_id: str | None
    template: dict
    scheduled_at: datetime | None
    status: str
    stats: dict
    sent_count: int
    delivered_count: int
    read_count: int
    clicked_count: int
    failed_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignScheduleIn(BaseModel):
    scheduled_at: datetime


# ─── Drip Sequences ───────────────────────────────────────────────────────────

class DripStepIn(BaseModel):
    step_order: int
    step_type: str  # message | condition | wait
    config: dict = Field(default_factory=dict)
    wait_minutes: int | None = None


class DripStepOut(BaseModel):
    id: str
    sequence_id: str
    step_order: int
    step_type: str
    config: dict
    wait_minutes: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class DripSequenceIn(BaseModel):
    name: str
    trigger_type: str  # first_contact | opt_in | tag_added | webhook
    trigger_config: dict = Field(default_factory=dict)
    steps: list[DripStepIn] = Field(default_factory=list)


class DripSequenceOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    trigger_type: str
    trigger_config: dict
    is_active: bool
    steps: list[DripStepOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class DripEnrollmentOut(BaseModel):
    id: str
    sequence_id: str
    contact_id: str
    current_step: int
    status: str
    next_send_at: datetime | None
    enrolled_at: datetime

    class Config:
        from_attributes = True


# ─── Products ─────────────────────────────────────────────────────────────────

class ProductIn(BaseModel):
    name: str
    description: str | None = None
    price_uzs: int = Field(..., ge=0)
    image_url: str | None = None
    checkout_url: str | None = None
    sku: str | None = None
    in_stock: bool = True
    extra: dict = Field(default_factory=dict)


class ProductOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    price_uzs: int
    image_url: str | None
    checkout_url: str | None
    sku: str | None
    in_stock: bool
    is_active: bool
    extra: dict
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Opt-in Links ─────────────────────────────────────────────────────────────

class OptInLinkIn(BaseModel):
    name: str
    platform: str
    channel_id: str | None = None
    welcome_message: str | None = None
    drip_sequence_id: str | None = None


class OptInLinkOut(BaseModel):
    id: str
    tenant_id: str
    slug: str
    name: str
    platform: str
    channel_id: str | None
    welcome_message: str | None
    drip_sequence_id: str | None
    scan_count: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
