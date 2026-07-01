"""Phase 12 — Growth layer router.

Endpoints:
  Contacts / CRM
    GET    /growth/contacts                  — list with filters & pagination
    GET    /growth/contacts/{id}             — detail
    PATCH  /growth/contacts/{id}             — update name/tags/notes
    POST   /growth/contacts/{id}/opt-in      — set opt_in flag + source
    POST   /growth/contacts/import           — bulk import from CSV JSON body
    DELETE /growth/contacts/{id}             — soft-delete (opt_out)

  Segments
    GET    /growth/segments                  — list
    POST   /growth/segments                  — create
    GET    /growth/segments/{id}             — detail
    PUT    /growth/segments/{id}             — update
    DELETE /growth/segments/{id}
    POST   /growth/segments/{id}/preview     — count + sample of matching contacts

  Campaigns (broadcast)
    GET    /growth/campaigns                 — list
    POST   /growth/campaigns                 — create draft
    GET    /growth/campaigns/{id}            — detail with metrics
    PUT    /growth/campaigns/{id}            — update draft
    DELETE /growth/campaigns/{id}
    POST   /growth/campaigns/{id}/schedule   — schedule send
    POST   /growth/campaigns/{id}/send-now   — immediate send (dev/test)
    POST   /growth/campaigns/{id}/pause
    POST   /growth/campaigns/{id}/cancel

  Drip Sequences
    GET    /growth/drip-sequences
    POST   /growth/drip-sequences
    GET    /growth/drip-sequences/{id}
    PUT    /growth/drip-sequences/{id}
    DELETE /growth/drip-sequences/{id}
    POST   /growth/drip-sequences/{id}/activate
    POST   /growth/drip-sequences/{id}/deactivate

  Products / Catalog
    GET    /growth/products
    POST   /growth/products
    GET    /growth/products/{id}
    PUT    /growth/products/{id}
    DELETE /growth/products/{id}

  Opt-in Links
    GET    /growth/opt-in-links
    POST   /growth/opt-in-links
    DELETE /growth/opt-in-links/{id}
    GET    /opt-in/{slug}                    — public redirect (no auth)
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.deps import CurrentTenant, CurrentUser
from javobai.db.models import (
    Campaign,
    CampaignRecipient,
    Contact,
    DripEnrollment,
    DripSequence,
    DripStep,
    OptInLink,
    Product,
    Segment,
)
from javobai.db.session import get_db
from javobai.growth.schemas import (
    CampaignIn,
    CampaignOut,
    CampaignScheduleIn,
    ContactOptInIn,
    ContactOut,
    ContactUpdateIn,
    DripEnrollmentOut,
    DripSequenceIn,
    DripSequenceOut,
    DripStepOut,
    OptInLinkIn,
    OptInLinkOut,
    ProductIn,
    ProductOut,
    SegmentIn,
    SegmentOut,
    SegmentPreviewOut,
)
from javobai.db.base import new_uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/growth", tags=["growth"])
public_router = APIRouter(tags=["growth-public"])

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _gen_slug(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _apply_segment_filters(query, filters: dict, tenant_id: str):
    """Apply segment filter dict to a Contact select query."""
    if tags := filters.get("tags"):
        # JSON contains check — works for Postgres JSON array
        for tag in tags:
            query = query.where(Contact.tags.contains([tag]))
    if opt_in := filters.get("opt_in"):
        query = query.where(Contact.opt_in == opt_in)
    if platform := filters.get("platform"):
        query = query.where(Contact.platform == platform)
    return query


# ─────────────────────────────────────────────────────────────────────────────
# Contacts
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/contacts", response_model=list[ContactOut])
async def list_contacts(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    platform: str | None = Query(None),
    opt_in: bool | None = Query(None),
    tag: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> list[ContactOut]:
    q = select(Contact).where(Contact.tenant_id == tenant.id)
    if platform:
        q = q.where(Contact.platform == platform)
    if opt_in is not None:
        q = q.where(Contact.opt_in == opt_in)
    if tag:
        q = q.where(Contact.tags.contains([tag]))
    if search:
        q = q.where(
            or_(
                Contact.name.ilike(f"%{search}%"),
                Contact.phone.ilike(f"%{search}%"),
                Contact.email.ilike(f"%{search}%"),
                Contact.external_user_id.ilike(f"%{search}%"),
            )
        )
    q = q.order_by(Contact.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return [ContactOut.model_validate(c) for c in result.scalars().all()]


@router.get("/contacts/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContactOut:
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.tenant_id == tenant.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return ContactOut.model_validate(contact)


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: str,
    body: ContactUpdateIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContactOut:
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.tenant_id == tenant.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(contact, field, val)
    await db.commit()
    await db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.post("/contacts/{contact_id}/opt-in", response_model=ContactOut)
async def set_opt_in(
    contact_id: str,
    body: ContactOptInIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContactOut:
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.tenant_id == tenant.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    now = datetime.now(UTC)
    if body.opt_in and not contact.opt_in:
        contact.opt_in = True
        contact.opt_in_at = now
        contact.opt_in_source = body.source or "manual"
        contact.opt_out_at = None
    elif not body.opt_in and contact.opt_in:
        contact.opt_in = False
        contact.opt_out_at = now

    await db.commit()
    await db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id, Contact.tenant_id == tenant.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    # Opt-out on delete (compliance: keep record, remove marketing consent)
    contact.opt_in = False
    contact.opt_out_at = datetime.now(UTC)
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Segments
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/segments", response_model=list[SegmentOut])
async def list_segments(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SegmentOut]:
    result = await db.execute(
        select(Segment).where(Segment.tenant_id == tenant.id).order_by(Segment.created_at.desc())
    )
    return [SegmentOut.model_validate(s) for s in result.scalars().all()]


@router.post("/segments", response_model=SegmentOut, status_code=status.HTTP_201_CREATED)
async def create_segment(
    body: SegmentIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SegmentOut:
    seg = Segment(tenant_id=tenant.id, name=body.name, filters=body.filters)
    db.add(seg)
    await db.commit()
    await db.refresh(seg)
    return SegmentOut.model_validate(seg)


@router.get("/segments/{segment_id}", response_model=SegmentOut)
async def get_segment(
    segment_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SegmentOut:
    result = await db.execute(
        select(Segment).where(Segment.id == segment_id, Segment.tenant_id == tenant.id)
    )
    seg = result.scalar_one_or_none()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    return SegmentOut.model_validate(seg)


@router.put("/segments/{segment_id}", response_model=SegmentOut)
async def update_segment(
    segment_id: str,
    body: SegmentIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SegmentOut:
    result = await db.execute(
        select(Segment).where(Segment.id == segment_id, Segment.tenant_id == tenant.id)
    )
    seg = result.scalar_one_or_none()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    seg.name = body.name
    seg.filters = body.filters
    await db.commit()
    await db.refresh(seg)
    return SegmentOut.model_validate(seg)


@router.delete("/segments/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    segment_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(Segment).where(Segment.id == segment_id, Segment.tenant_id == tenant.id)
    )
    seg = result.scalar_one_or_none()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    await db.delete(seg)
    await db.commit()


@router.post("/segments/{segment_id}/preview", response_model=SegmentPreviewOut)
async def preview_segment(
    segment_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SegmentPreviewOut:
    result = await db.execute(
        select(Segment).where(Segment.id == segment_id, Segment.tenant_id == tenant.id)
    )
    seg = result.scalar_one_or_none()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")

    q = select(Contact).where(Contact.tenant_id == tenant.id)
    q = _apply_segment_filters(q, seg.filters, tenant.id)

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    count = count_result.scalar_one()

    sample_result = await db.execute(q.limit(5))
    sample = [ContactOut.model_validate(c) for c in sample_result.scalars().all()]

    return SegmentPreviewOut(count=count, sample=sample)


# ─────────────────────────────────────────────────────────────────────────────
# Campaigns
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/campaigns", response_model=list[CampaignOut])
async def list_campaigns(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    campaign_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> list[CampaignOut]:
    q = select(Campaign).where(Campaign.tenant_id == tenant.id)
    if campaign_type:
        q = q.where(Campaign.campaign_type == campaign_type)
    if status_filter:
        q = q.where(Campaign.status == status_filter)
    q = q.order_by(Campaign.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return [CampaignOut.model_validate(c) for c in result.scalars().all()]


@router.post("/campaigns", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignOut:
    camp = Campaign(
        tenant_id=tenant.id,
        name=body.name,
        campaign_type=body.campaign_type,
        segment_id=body.segment_id,
        template=body.template,
        scheduled_at=body.scheduled_at,
        status="draft",
        stats={},
        sent_count=0,
        delivered_count=0,
        read_count=0,
        clicked_count=0,
        failed_count=0,
    )
    db.add(camp)
    await db.commit()
    await db.refresh(camp)
    return CampaignOut.model_validate(camp)


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignOut:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant.id)
    )
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignOut.model_validate(camp)


@router.put("/campaigns/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: str,
    body: CampaignIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignOut:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant.id)
    )
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail="Only draft/scheduled campaigns can be edited")
    camp.name = body.name
    camp.segment_id = body.segment_id
    camp.template = body.template
    camp.scheduled_at = body.scheduled_at
    await db.commit()
    await db.refresh(camp)
    return CampaignOut.model_validate(camp)


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant.id)
    )
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete a running campaign")
    await db.delete(camp)
    await db.commit()


@router.post("/campaigns/{campaign_id}/schedule", response_model=CampaignOut)
async def schedule_campaign(
    campaign_id: str,
    body: CampaignScheduleIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignOut:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant.id)
    )
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status not in ("draft",):
        raise HTTPException(status_code=400, detail="Only draft campaigns can be scheduled")
    if not camp.template:
        raise HTTPException(status_code=400, detail="Campaign must have a template before scheduling")

    camp.scheduled_at = body.scheduled_at
    camp.status = "scheduled"
    await db.commit()
    await db.refresh(camp)
    logger.info("Campaign %s scheduled for %s (tenant=%s)", campaign_id, body.scheduled_at, tenant.id)
    return CampaignOut.model_validate(camp)


@router.post("/campaigns/{campaign_id}/send-now", response_model=CampaignOut)
async def send_campaign_now(
    campaign_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignOut:
    """Immediately transition campaign to running and enqueue recipients.
    
    In production this triggers a worker job; for MVP we mark it running
    and create CampaignRecipient rows for tracking.
    """
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant.id)
    )
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail="Campaign is already running or completed")
    if not camp.segment_id:
        raise HTTPException(status_code=400, detail="Campaign must have a segment to send")

    # Fetch opted-in contacts from segment
    seg_result = await db.execute(
        select(Segment).where(Segment.id == camp.segment_id, Segment.tenant_id == tenant.id)
    )
    seg = seg_result.scalar_one_or_none()
    if not seg:
        raise HTTPException(status_code=400, detail="Segment not found")

    q = select(Contact).where(Contact.tenant_id == tenant.id, Contact.opt_in == True)  # noqa: E712
    q = _apply_segment_filters(q, seg.filters, tenant.id)
    contacts_result = await db.execute(q)
    contacts = contacts_result.scalars().all()

    if not contacts:
        raise HTTPException(status_code=400, detail="No opted-in contacts in this segment")

    now = datetime.now(UTC)
    # Create recipient rows
    for contact in contacts:
        recipient = CampaignRecipient(
            id=new_uuid(),
            campaign_id=camp.id,
            contact_id=contact.id,
            tenant_id=tenant.id,
            status="queued",
            created_at=now,
        )
        db.add(recipient)

    camp.status = "running"
    camp.scheduled_at = now
    await db.commit()
    await db.refresh(camp)
    logger.info(
        "Campaign %s started with %d recipients (tenant=%s)",
        campaign_id, len(contacts), tenant.id,
    )
    return CampaignOut.model_validate(camp)


@router.post("/campaigns/{campaign_id}/pause", response_model=CampaignOut)
async def pause_campaign(
    campaign_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignOut:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant.id)
    )
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status != "running":
        raise HTTPException(status_code=400, detail="Only running campaigns can be paused")
    camp.status = "paused"
    await db.commit()
    await db.refresh(camp)
    return CampaignOut.model_validate(camp)


@router.post("/campaigns/{campaign_id}/cancel", response_model=CampaignOut)
async def cancel_campaign(
    campaign_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignOut:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant.id)
    )
    camp = result.scalar_one_or_none()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status in ("completed", "failed"):
        raise HTTPException(status_code=400, detail="Campaign already finished")
    camp.status = "failed"
    await db.commit()
    await db.refresh(camp)
    return CampaignOut.model_validate(camp)


# ─────────────────────────────────────────────────────────────────────────────
# Drip Sequences
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/drip-sequences", response_model=list[DripSequenceOut])
async def list_drip_sequences(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[DripSequenceOut]:
    result = await db.execute(
        select(DripSequence)
        .where(DripSequence.tenant_id == tenant.id)
        .order_by(DripSequence.created_at.desc())
    )
    sequences = result.scalars().all()
    out = []
    for seq in sequences:
        steps_result = await db.execute(
            select(DripStep)
            .where(DripStep.sequence_id == seq.id)
            .order_by(DripStep.step_order)
        )
        steps = [DripStepOut.model_validate(s) for s in steps_result.scalars().all()]
        seq_out = DripSequenceOut.model_validate(seq)
        seq_out.steps = steps
        out.append(seq_out)
    return out


@router.post("/drip-sequences", response_model=DripSequenceOut, status_code=status.HTTP_201_CREATED)
async def create_drip_sequence(
    body: DripSequenceIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DripSequenceOut:
    seq = DripSequence(
        tenant_id=tenant.id,
        name=body.name,
        trigger_type=body.trigger_type,
        trigger_config=body.trigger_config,
        is_active=False,
    )
    db.add(seq)
    await db.flush()

    now = datetime.now(UTC)
    steps = []
    for step_in in body.steps:
        step = DripStep(
            id=new_uuid(),
            sequence_id=seq.id,
            tenant_id=tenant.id,
            step_order=step_in.step_order,
            step_type=step_in.step_type,
            config=step_in.config,
            wait_minutes=step_in.wait_minutes,
            created_at=now,
        )
        db.add(step)
        steps.append(step)

    await db.commit()
    await db.refresh(seq)
    seq_out = DripSequenceOut.model_validate(seq)
    seq_out.steps = [DripStepOut.model_validate(s) for s in steps]
    return seq_out


@router.get("/drip-sequences/{seq_id}", response_model=DripSequenceOut)
async def get_drip_sequence(
    seq_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DripSequenceOut:
    result = await db.execute(
        select(DripSequence).where(DripSequence.id == seq_id, DripSequence.tenant_id == tenant.id)
    )
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    steps_result = await db.execute(
        select(DripStep).where(DripStep.sequence_id == seq_id).order_by(DripStep.step_order)
    )
    steps = [DripStepOut.model_validate(s) for s in steps_result.scalars().all()]
    seq_out = DripSequenceOut.model_validate(seq)
    seq_out.steps = steps
    return seq_out


@router.put("/drip-sequences/{seq_id}", response_model=DripSequenceOut)
async def update_drip_sequence(
    seq_id: str,
    body: DripSequenceIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DripSequenceOut:
    result = await db.execute(
        select(DripSequence).where(DripSequence.id == seq_id, DripSequence.tenant_id == tenant.id)
    )
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")

    seq.name = body.name
    seq.trigger_type = body.trigger_type
    seq.trigger_config = body.trigger_config

    # Replace steps
    old_steps = await db.execute(select(DripStep).where(DripStep.sequence_id == seq_id))
    for s in old_steps.scalars().all():
        await db.delete(s)

    now = datetime.now(UTC)
    new_steps = []
    for step_in in body.steps:
        step = DripStep(
            id=new_uuid(),
            sequence_id=seq.id,
            tenant_id=tenant.id,
            step_order=step_in.step_order,
            step_type=step_in.step_type,
            config=step_in.config,
            wait_minutes=step_in.wait_minutes,
            created_at=now,
        )
        db.add(step)
        new_steps.append(step)

    await db.commit()
    await db.refresh(seq)
    seq_out = DripSequenceOut.model_validate(seq)
    seq_out.steps = [DripStepOut.model_validate(s) for s in new_steps]
    return seq_out


@router.delete("/drip-sequences/{seq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_drip_sequence(
    seq_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(DripSequence).where(DripSequence.id == seq_id, DripSequence.tenant_id == tenant.id)
    )
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    await db.delete(seq)
    await db.commit()


@router.post("/drip-sequences/{seq_id}/activate", response_model=DripSequenceOut)
async def activate_sequence(
    seq_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DripSequenceOut:
    result = await db.execute(
        select(DripSequence).where(DripSequence.id == seq_id, DripSequence.tenant_id == tenant.id)
    )
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    seq.is_active = True
    await db.commit()
    await db.refresh(seq)
    seq_out = DripSequenceOut.model_validate(seq)
    return seq_out


@router.post("/drip-sequences/{seq_id}/deactivate", response_model=DripSequenceOut)
async def deactivate_sequence(
    seq_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DripSequenceOut:
    result = await db.execute(
        select(DripSequence).where(DripSequence.id == seq_id, DripSequence.tenant_id == tenant.id)
    )
    seq = result.scalar_one_or_none()
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    seq.is_active = False
    await db.commit()
    await db.refresh(seq)
    seq_out = DripSequenceOut.model_validate(seq)
    return seq_out


# ─────────────────────────────────────────────────────────────────────────────
# Products / Catalog
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/products", response_model=list[ProductOut])
async def list_products(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
    in_stock: bool | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> list[ProductOut]:
    q = select(Product).where(Product.tenant_id == tenant.id, Product.is_active == True)  # noqa: E712
    if in_stock is not None:
        q = q.where(Product.in_stock == in_stock)
    q = q.order_by(Product.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return [ProductOut.model_validate(p) for p in result.scalars().all()]


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    product = Product(tenant_id=tenant.id, **body.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return ProductOut.model_validate(product)


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.model_validate(product)


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str,
    body: ProductIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductOut:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, val in body.model_dump().items():
        setattr(product, field, val)
    await db.commit()
    await db.refresh(product)
    return ProductOut.model_validate(product)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.is_active = False  # Soft delete
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Opt-in Links
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/opt-in-links", response_model=list[OptInLinkOut])
async def list_opt_in_links(
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OptInLinkOut]:
    result = await db.execute(
        select(OptInLink)
        .where(OptInLink.tenant_id == tenant.id)
        .order_by(OptInLink.created_at.desc())
    )
    return [OptInLinkOut.model_validate(l) for l in result.scalars().all()]  # noqa: E741


@router.post("/opt-in-links", response_model=OptInLinkOut, status_code=status.HTTP_201_CREATED)
async def create_opt_in_link(
    body: OptInLinkIn,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OptInLinkOut:
    # Generate unique slug
    slug = _gen_slug()
    for _ in range(5):
        existing = await db.execute(select(OptInLink).where(OptInLink.slug == slug))
        if not existing.scalar_one_or_none():
            break
        slug = _gen_slug()

    link = OptInLink(
        id=new_uuid(),
        tenant_id=tenant.id,
        slug=slug,
        name=body.name,
        platform=body.platform,
        channel_id=body.channel_id,
        welcome_message=body.welcome_message,
        drip_sequence_id=body.drip_sequence_id,
        scan_count=0,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return OptInLinkOut.model_validate(link)


@router.delete("/opt-in-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opt_in_link(
    link_id: str,
    tenant: CurrentTenant,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(
        select(OptInLink).where(OptInLink.id == link_id, OptInLink.tenant_id == tenant.id)
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Opt-in link not found")
    link.is_active = False
    await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Public opt-in redirect (no auth)
# ─────────────────────────────────────────────────────────────────────────────

@public_router.get("/opt-in/{slug}")
async def opt_in_redirect(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Public endpoint — increments scan_count and returns link info for redirect."""
    result = await db.execute(
        select(OptInLink).where(OptInLink.slug == slug, OptInLink.is_active == True)  # noqa: E712
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found or inactive")

    link.scan_count = (link.scan_count or 0) + 1
    await db.commit()

    # Build platform-specific deep link
    redirect_url: str | None = None
    if link.platform == "telegram" and link.channel_id:
        # Return info; client builds t.me link
        pass
    elif link.platform == "whatsapp":
        # wa.me link
        pass

    return {
        "slug": slug,
        "platform": link.platform,
        "welcome_message": link.welcome_message,
        "scan_count": link.scan_count,
    }
