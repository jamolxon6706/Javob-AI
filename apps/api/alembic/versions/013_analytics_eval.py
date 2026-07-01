"""013 analytics + AI eval harness — per-answer audit trail, golden test sets

Revision ID: 013_analytics_eval
Revises: 012_growth_layer
Create Date: 2026-06-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "013_analytics_eval"
down_revision = "012_growth_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- messages: per-answer audit trail (ARCHITECTURE.md Phase 13) ---
    # `source` and `rag_score` already exist (Phase 3/5). These add the rest
    # of "which path: rule/faq/llm/action, model, score, latency, cost".
    op.add_column("messages", sa.Column("model", sa.String(100), nullable=True))
    op.add_column("messages", sa.Column("latency_ms", sa.Integer, nullable=True))
    op.add_column(
        "messages",
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
    )
    # angry | neutral | positive — tagged on inbound messages only.
    op.add_column("messages", sa.Column("sentiment", sa.String(20), nullable=True))

    # --- conversations: why a handoff happened, for analytics grouping ---
    op.add_column("conversations", sa.Column("handoff_reason", sa.String(50), nullable=True))

    # --- eval_cases: golden test set per tenant ---
    op.create_table(
        "eval_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="uz"),
        # If set, retrieval must return this FAQ as the top match to pass.
        sa.Column(
            "expected_faq_id", sa.String(36), sa.ForeignKey("faqs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # If set (and expected_faq_id is not), the returned answer must contain
        # this substring (case-insensitive) to pass — supports LLM-path cases.
        sa.Column("expected_answer_contains", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- eval_runs: one row per harness execution ---
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("passed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer, nullable=False, server_default="0"),
        # True when pass-rate dropped more than the configured threshold vs.
        # the previous run — surfaced as a CI-style regression flag.
        sa.Column("is_regression", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- eval_results: per-case outcome within a run ---
    op.create_table(
        "eval_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "eval_run_id", sa.String(36), sa.ForeignKey("eval_runs.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "eval_case_id", sa.String(36), sa.ForeignKey("eval_cases.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("actual_source", sa.String(50), nullable=True),
        sa.Column("actual_faq_id", sa.String(36), nullable=True),
        sa.Column("actual_score", sa.Float, nullable=True),
        sa.Column("actual_answer", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("eval_results")
    op.drop_table("eval_runs")
    op.drop_table("eval_cases")
    op.drop_column("conversations", "handoff_reason")
    op.drop_column("messages", "sentiment")
    op.drop_column("messages", "cost_usd")
    op.drop_column("messages", "latency_ms")
    op.drop_column("messages", "model")
