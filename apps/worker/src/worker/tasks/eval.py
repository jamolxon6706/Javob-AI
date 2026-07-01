from __future__ import annotations

import logging

from worker.services.eval import EvalHarness

logger = logging.getLogger(__name__)


async def run_eval_job(ctx: dict, tenant_id: str) -> dict:  # type: ignore[type-arg]
    """
    Run the AI eval harness (golden test set) for one tenant and persist the
    result. Triggered from the dashboard's "Run eval" button — the API just
    enqueues this job and the frontend polls GET /analytics/quality for the
    result (see javobai.analytics.router).
    """
    rag = ctx["rag"]
    emb = ctx["embedding"]
    pool = ctx["db_pool"]

    harness = EvalHarness(emb, rag)
    async with pool.acquire() as conn:
        summary = await harness.run(tenant_id, conn)

    return {
        "run_id": summary.id,
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failed,
        "is_regression": summary.is_regression,
    }
