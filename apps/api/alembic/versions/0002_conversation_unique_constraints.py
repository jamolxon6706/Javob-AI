"""conversation/contact unique constraints for idempotent upserts

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-16
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_contacts_tenant_platform_external",
        "contacts",
        ["tenant_id", "platform", "external_user_id"],
    )
    op.create_unique_constraint(
        "uq_conversations_channel_contact",
        "conversations",
        ["channel_id", "contact_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_conversations_channel_contact", "conversations", type_="unique")
    op.drop_constraint("uq_contacts_tenant_platform_external", "contacts", type_="unique")
