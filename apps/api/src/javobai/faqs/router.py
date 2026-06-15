from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.deps import CurrentTenant, CurrentUser
from javobai.db.models import FAQ, Tenant
from javobai.db.session import get_db

router = APIRouter(prefix="/faqs", tags=["faqs"])


class FAQIn(BaseModel):
    question: str
    answer: str
    category: str | None = None
    language: str = "uz"


class FAQOut(BaseModel):
    id: str
    tenant_id: str
    question: str
    answer: str
    category: str | None
    language: str
    is_active: bool


class FAQUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    category: str | None = None
    language: str | None = None
    is_active: bool | None = None


def _to_out(faq: FAQ) -> FAQOut:
    return FAQOut(
        id=faq.id,
        tenant_id=faq.tenant_id,
        question=faq.question,
        answer=faq.answer,
        category=faq.category,
        language=faq.language,
        is_active=faq.is_active,
    )


@router.get("", response_model=list[FAQOut])
async def list_faqs(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[FAQOut]:
    result = await db.execute(
        select(FAQ).where(FAQ.tenant_id == tenant.id).order_by(FAQ.created_at.desc())
    )
    return [_to_out(f) for f in result.scalars().all()]


@router.post("", response_model=FAQOut, status_code=status.HTTP_201_CREATED)
async def create_faq(
    body: FAQIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FAQOut:
    faq = FAQ(
        tenant_id=tenant.id,
        question=body.question,
        answer=body.answer,
        category=body.category,
        language=body.language,
    )
    db.add(faq)
    await db.flush()
    return _to_out(faq)


@router.get("/{faq_id}", response_model=FAQOut)
async def get_faq(
    faq_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FAQOut:
    result = await db.execute(
        select(FAQ).where(FAQ.id == faq_id, FAQ.tenant_id == tenant.id)
    )
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
    return _to_out(faq)


@router.patch("/{faq_id}", response_model=FAQOut)
async def update_faq(
    faq_id: str,
    body: FAQUpdate,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FAQOut:
    result = await db.execute(
        select(FAQ).where(FAQ.id == faq_id, FAQ.tenant_id == tenant.id)
    )
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(faq, field, value)
    await db.flush()
    return _to_out(faq)


@router.delete("/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(
    faq_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(FAQ).where(FAQ.id == faq_id, FAQ.tenant_id == tenant.id)
    )
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
    await db.delete(faq)
