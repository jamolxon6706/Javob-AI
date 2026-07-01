from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.deps import CurrentTenant
from javobai.db.models import Rule
from javobai.db.session import get_db

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleIn(BaseModel):
    name: str
    trigger_type: str
    trigger_value: dict = {}  # type: ignore[type-arg]
    action_type: str
    action_value: dict = {}  # type: ignore[type-arg]
    priority: int = 0
    is_active: bool = True


class RuleOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    trigger_type: str
    trigger_value: dict  # type: ignore[type-arg]
    action_type: str
    action_value: dict  # type: ignore[type-arg]
    priority: int
    is_active: bool


class RuleUpdate(BaseModel):
    name: str | None = None
    trigger_type: str | None = None
    trigger_value: dict | None = None  # type: ignore[type-arg]
    action_type: str | None = None
    action_value: dict | None = None  # type: ignore[type-arg]
    priority: int | None = None
    is_active: bool | None = None


def _to_out(rule: Rule) -> RuleOut:
    return RuleOut(
        id=rule.id,
        tenant_id=rule.tenant_id,
        name=rule.name,
        trigger_type=rule.trigger_type,
        trigger_value=rule.trigger_value or {},
        action_type=rule.action_type,
        action_value=rule.action_value or {},
        priority=rule.priority,
        is_active=rule.is_active,
    )


@router.get("", response_model=list[RuleOut])
async def list_rules(
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db),
) -> list[RuleOut]:
    result = await db.execute(
        select(Rule)
        .where(Rule.tenant_id == tenant.id)
        .order_by(Rule.priority.desc(), Rule.created_at.desc())
    )
    return [_to_out(r) for r in result.scalars().all()]


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleIn,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db),
) -> RuleOut:
    rule = Rule(
        tenant_id=tenant.id,
        name=body.name,
        trigger_type=body.trigger_type,
        trigger_value=body.trigger_value,
        action_type=body.action_type,
        action_value=body.action_value,
        priority=body.priority,
        is_active=body.is_active,
    )
    db.add(rule)
    await db.flush()
    return _to_out(rule)


@router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: str,
    body: RuleUpdate,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db),
) -> RuleOut:
    result = await db.execute(
        select(Rule).where(Rule.id == rule_id, Rule.tenant_id == tenant.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    await db.flush()
    return _to_out(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Rule).where(Rule.id == rule_id, Rule.tenant_id == tenant.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    await db.delete(rule)
