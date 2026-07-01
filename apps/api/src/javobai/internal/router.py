"""
Internal / developer routes — not exposed in production.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.deps import CurrentTenant
from javobai.config import settings
from javobai.db.session import get_db

router = APIRouter(prefix="/internal", tags=["internal"])


class EmbedIn(BaseModel):
    text: str


class EmbedOut(BaseModel):
    embedding: list[float]
    dim: int


@router.post("/embed", response_model=EmbedOut)
async def embed_text(body: EmbedIn, request: Request) -> EmbedOut:
    try:
        job = await request.app.state.arq.enqueue_job("probe_embed_job", body.text)
        result: list[float] = await job.result(timeout=30.0, poll_delay=0.5)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding job failed: {exc}") from exc
    return EmbedOut(embedding=result, dim=len(result))


class RAGTestIn(BaseModel):
    query: str
    top_k: int = 5


class RAGHit(BaseModel):
    id: str
    question: str
    answer: str
    category: str | None
    language: str
    score: float


class RAGTestOut(BaseModel):
    query: str
    results: list[RAGHit]


@router.post("/rag-test", response_model=RAGTestOut)
async def rag_test(
    body: RAGTestIn,
    request: Request,
    tenant: CurrentTenant,
    db: AsyncSession = Depends(get_db),
) -> RAGTestOut:
    """Live RAG search — returns matched FAQs with cosine scores. Dev only."""
    import httpx
    from javobai.db.models import FAQ

    # Embed via the worker's probe endpoint (reuses loaded bge-m3 model)
    try:
        job = await request.app.state.arq.enqueue_job("probe_embed_job", body.query)
        embedding: list[float] = await job.result(timeout=30.0, poll_delay=0.5)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding unavailable: {exc}") from exc

    result = await db.execute(
        select(FAQ, FAQ.embedding.cosine_distance(embedding).label("distance"))
        .where(FAQ.tenant_id == tenant.id, FAQ.is_active.is_(True), FAQ.embedding.is_not(None))
        .order_by("distance")
        .limit(body.top_k)
    )
    rows = result.all()
    hits = [
        RAGHit(
            id=faq.id,
            question=faq.question,
            answer=faq.answer,
            category=faq.category,
            language=faq.language,
            score=round(1 - distance, 4),
        )
        for faq, distance in rows
    ]
    return RAGTestOut(query=body.query, results=hits)
