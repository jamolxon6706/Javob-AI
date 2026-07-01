from pydantic import BaseModel, Field
from typing import Optional


class MetaChannelConnect(BaseModel):
    """Request body for connecting an IG or FB page channel."""

    platform: str = Field(..., pattern=r"^(instagram|facebook)$")
    access_token: str = Field(..., min_length=10)
    # Only required for WhatsApp (Phase 9), optional here
    phone_number_id: Optional[str] = None


class MetaChannelStatus(BaseModel):
    id: str
    platform: str
    page_id: str
    page_name: str
    status: str
    permissions_ok: bool = True
    missing_permissions: list[str] = []
