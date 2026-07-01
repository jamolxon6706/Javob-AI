"""011 agentic flows and actions

Revision ID: 011_agentic_flows
Revises: 010_previous
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "011_agentic_flows"
down_revision = "010_meta_adapters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tenant_actions
    op.create_table(
        "tenant_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("params_schema", sa.JSON, nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("webhook_url", sa.String(500), nullable=True),
        sa.Column("webhook_secret", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_tenant_actions_tenant", "tenant_actions", ["tenant_id"])
    op.create_unique_constraint(
        "uq_tenant_action_name", "tenant_actions", ["tenant_id", "name"]
    )

    # action_logs
    op.create_table(
        "action_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "action_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenant_actions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action_name", sa.String(100), nullable=False),
        sa.Column("inputs", sa.JSON, nullable=True),
        sa.Column("outputs", sa.JSON, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.String(20), nullable=True),
        sa.Column(
            "called_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_action_logs_tenant", "action_logs", ["tenant_id"])
    op.create_index("ix_action_logs_action", "action_logs", ["action_id"])

    # flows
    op.create_table(
        "flows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_config", sa.JSON, nullable=True),
        sa.Column("nodes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("edges", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_flows_tenant", "flows", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("flows")
    op.drop_index("ix_action_logs_action", "action_logs")
    op.drop_index("ix_action_logs_tenant", "action_logs")
    op.drop_table("action_logs")
    op.drop_index("ix_tenant_actions_tenant", "tenant_actions")
    op.drop_table("tenant_actions")
