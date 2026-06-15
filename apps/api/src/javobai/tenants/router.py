from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.deps import CurrentTenant, CurrentUser
from javobai.db.models import Tenant
from javobai.db.session import get_db

router = APIRouter(prefix="/tenants", tags=["tenants"])


class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    is_active: bool


class TenantUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None  # type: ignore[type-arg]


@router.get("/me", response_model=TenantOut)
async def get_my_tenant(tenant: CurrentTenant) -> TenantOut:
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan=tenant.plan,
        is_active=tenant.is_active,
    )


@router.patch("/me", response_model=TenantOut)
async def update_my_tenant(
    body: TenantUpdate,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantOut:
    if body.name is not None:
        tenant.name = body.name
    if body.settings is not None:
        tenant.settings = body.settings
    await db.flush()
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        plan=tenant.plan,
        is_active=tenant.is_active,
    )
