from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from javobai.db.session import get_db
from javobai.db.models.flow import Flow
from javobai.schemas.flow import FlowCreate, FlowUpdate, FlowRead
from javobai.auth.deps import get_current_tenant

router = APIRouter(prefix="/flows", tags=["flows"])


@router.get("", response_model=List[FlowRead])
async def list_flows(
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Flow)
        .where(Flow.tenant_id == tenant.id)
        .order_by(Flow.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=FlowRead, status_code=status.HTTP_201_CREATED)
async def create_flow(
    body: FlowCreate,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    flow = Flow(tenant_id=tenant.id, **body.model_dump())
    db.add(flow)
    await db.commit()
    await db.refresh(flow)
    return flow


@router.get("/{flow_id}", response_model=FlowRead)
async def get_flow(
    flow_id: UUID,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Flow).where(
            Flow.id == flow_id,
            Flow.tenant_id == tenant.id,
        )
    )
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


@router.put("/{flow_id}", response_model=FlowRead)
async def update_flow(
    flow_id: UUID,
    body: FlowUpdate,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Flow).where(
            Flow.id == flow_id,
            Flow.tenant_id == tenant.id,
        )
    )
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(flow, field, value)

    await db.commit()
    await db.refresh(flow)
    return flow


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(
    flow_id: UUID,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Flow).where(
            Flow.id == flow_id,
            Flow.tenant_id == tenant.id,
        )
    )
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    await db.delete(flow)
    await db.commit()


@router.post("/{flow_id}/activate", response_model=FlowRead)
async def activate_flow(
    flow_id: UUID,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Flow).where(
            Flow.id == flow_id,
            Flow.tenant_id == tenant.id,
        )
    )
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    flow.is_active = True
    await db.commit()
    await db.refresh(flow)
    return flow


@router.post("/{flow_id}/deactivate", response_model=FlowRead)
async def deactivate_flow(
    flow_id: UUID,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Flow).where(
            Flow.id == flow_id,
            Flow.tenant_id == tenant.id,
        )
    )
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    flow.is_active = False
    await db.commit()
    await db.refresh(flow)
    return flow
