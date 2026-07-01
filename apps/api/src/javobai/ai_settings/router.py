from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.deps import CurrentTenant
from javobai.db.models import Tenant
from javobai.db.session import get_db

router = APIRouter(prefix="/ai-settings", tags=["ai-settings"])


class AISettingsOut(BaseModel):
    brand_voice: str
    confidence_threshold: float
    llm_enabled: bool
    banned_topics: list[str]
    language_mode: str  # auto | uz | ru


class AISettingsUpdate(BaseModel):
    brand_voice: str | None = None
    confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)
    llm_enabled: bool | None = None
    banned_topics: list[str] | None = None
    language_mode: str | None = None


def _extract(tenant: Tenant) -> AISettingsOut:
    s: dict = tenant.settings or {}  # type: ignore[assignment]
    ai: dict = s.get("ai", {})
    return AISettingsOut(
        brand_voice=ai.get("brand_voice", ""),
        confidence_threshold=ai.get("confidence_threshold", 0.65),
        llm_enabled=ai.get("llm_enabled", True),
        banned_topics=ai.get("banned_topics", []),
        language_mode=ai.get("language_mode", "auto"),
    )


@router.get("", response_model=AISettingsOut)
async def get_ai_settings(
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db),
) -> AISettingsOut:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant.id))
    t = result.scalar_one()
    return _extract(t)


@router.patch("", response_model=AISettingsOut)
async def update_ai_settings(
    body: AISettingsUpdate,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db),
) -> AISettingsOut:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant.id))
    t = result.scalar_one()
    s: dict = dict(t.settings or {})  # type: ignore[assignment]
    ai: dict = dict(s.get("ai", {}))
    for field, value in body.model_dump(exclude_none=True).items():
        ai[field] = value
    s["ai"] = ai
    t.settings = s
    await db.flush()
    return _extract(t)
