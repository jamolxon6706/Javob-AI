"""010 meta adapters - add meta_extra to messages

Revision ID: 010_meta_adapters
Revises: 009_previous
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "010_meta_adapters"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add meta_extra JSON column to messages table (nullable, IG/FB comment context)
    op.add_column(
        "messages",
        sa.Column("meta_extra", sa.JSON, nullable=True),
    )

    # Add external_message_id for dedup (if not already present from earlier phases)
    op.add_column(
        "messages",
        sa.Column("external_message_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_messages_external_id",
        "messages",
        ["platform", "external_message_id"],
    )

    # Add instagram and facebook to channels platform enum (if using enum)
    # If platform is a plain VARCHAR, no migration needed.
    # Uncomment below if you used a PG ENUM in an earlier phase:
    #
    # op.execute(
    #     "ALTER TYPE platform_enum ADD VALUE IF NOT EXISTS 'instagram';"
    # )
    # op.execute(
    #     "ALTER TYPE platform_enum ADD VALUE IF NOT EXISTS 'facebook';"
    # )


def downgrade() -> None:
    op.drop_index("ix_messages_external_id", "messages")
    op.drop_column("messages", "external_message_id")
    op.drop_column("messages", "meta_extra")
