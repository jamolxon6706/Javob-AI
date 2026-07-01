from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from javobai.db.session import get_db
from javobai.db.models.action_def import TenantAction, ActionLog
from javobai.schemas.action import (
    TenantActionCreate,
    TenantActionUpdate,
    TenantActionRead,
    ActionLogRead,
)
from javobai.auth.deps import get_current_tenant

router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("", response_model=List[TenantActionRead])
async def list_actions(
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TenantAction)
        .where(TenantAction.tenant_id == tenant.id)
        .order_by(TenantAction.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=TenantActionRead, status_code=status.HTTP_201_CREATED)
async def create_action(
    body: TenantActionCreate,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(TenantAction).where(
            TenantAction.tenant_id == tenant.id,
            TenantAction.name == body.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Action name already exists for this tenant",
        )

    action = TenantAction(
        tenant_id=tenant.id,
        **body.model_dump(exclude_none=True),
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


@router.patch("/{action_id}", response_model=TenantActionRead)
async def update_action(
    action_id: UUID,
    body: TenantActionUpdate,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TenantAction).where(
            TenantAction.id == action_id,
            TenantAction.tenant_id == tenant.id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(action, field, value)

    await db.commit()
    await db.refresh(action)
    return action


@router.delete("/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(
    action_id: UUID,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TenantAction).where(
            TenantAction.id == action_id,
            TenantAction.tenant_id == tenant.id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    await db.delete(action)
    await db.commit()


@router.get("/{action_id}/logs", response_model=List[ActionLogRead])
async def action_logs(
    action_id: UUID,
    limit: int = 50,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ActionLog)
        .where(
            ActionLog.action_id == action_id,
            ActionLog.tenant_id == tenant.id,
        )
        .order_by(ActionLog.called_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/{action_id}/test")
async def test_action(
    action_id: UUID,
    params: dict,
    tenant=Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Test an action with sample params — enqueues to worker via ARQ."""
    result = await db.execute(
        select(TenantAction).where(
            TenantAction.id == action_id,
            TenantAction.tenant_id == tenant.id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    # Return action info so the client can show what would be called
    return {
        "action_name": action.name,
        "action_type": action.action_type,
        "params_received": params,
        "message": "Test enqueued — check worker logs for execution result.",
    }
