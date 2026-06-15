"""
Internal / developer routes — not exposed in production.
Used to verify the worker's embedding model is working correctly.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/internal", tags=["internal"])


class EmbedIn(BaseModel):
    text: str


class EmbedOut(BaseModel):
    embedding: list[float]
    dim: int


@router.post("/embed", response_model=EmbedOut)
async def embed_text(body: EmbedIn, request: Request) -> EmbedOut:
    """
    Enqueue a test_embed_job to the worker and await its result.
    Verifies that bge-m3 is loaded and reachable from the API.
    Dev/staging only; not registered in production.
    """
    try:
        job = await request.app.state.arq.enqueue_job("probe_embed_job", body.text)
        result: list[float] = await job.result(timeout=30.0, poll_delay=0.5)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding job failed: {exc}") from exc
    return EmbedOut(embedding=result, dim=len(result))
