"""012 growth layer — contacts opt-in, broadcast metrics, drip sequences, catalog

Revision ID: 012_growth_layer
Revises: 011_agentic_flows
Create Date: 2026-06-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "012_growth_layer"
down_revision = "011_agentic_flows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- contacts: add consent & double opt-in cols (table already exists) ---
    op.add_column("contacts", sa.Column("double_opt_in_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contacts", sa.Column("double_opt_in_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contacts", sa.Column("opt_out_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contacts", sa.Column("notes", sa.Text, nullable=True))
    op.add_column("contacts", sa.Column("custom_fields", sa.JSON, nullable=True, server_default="{}"))

    # --- campaigns: add metrics + scheduling cols ---
    op.add_column("campaigns", sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id", ondelete="SET NULL"), nullable=True))
    op.add_column("campaigns", sa.Column("send_at", sa.DateTime(timezone=True), nullable=True))  # alias scheduled_at for clarity
    op.add_column("campaigns", sa.Column("sent_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("campaigns", sa.Column("delivered_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("campaigns", sa.Column("read_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("campaigns", sa.Column("clicked_count", sa.Integer, nullable=False, server_default="0"))
    op.add_column("campaigns", sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"))

    # --- drip_sequences ---
    op.create_table(
        "drip_sequences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        # trigger: first_contact | opt_in | tag_added | webhook
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # --- drip_steps ---
    op.create_table(
        "drip_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sequence_id", sa.String(36), sa.ForeignKey("drip_sequences.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("step_order", sa.Integer, nullable=False),
        # message | condition | wait
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("config", sa.JSON, nullable=False, server_default="{}"),
        # wait_minutes for wait steps
        sa.Column("wait_minutes", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- drip_enrollments (contact enrolled in a sequence) ---
    op.create_table(
        "drip_enrollments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sequence_id", sa.String(36), sa.ForeignKey("drip_sequences.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="0"),
        # active | paused | completed | unsubscribed
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("sequence_id", "contact_id", name="uq_drip_enrollment"),
    )

    # --- products (catalog) ---
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("price_uzs", sa.Integer, nullable=False),  # price in UZS tiyin
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("checkout_url", sa.String(500), nullable=True),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("in_stock", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("extra", sa.JSON, nullable=True, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- campaign_recipients (per-contact status for broadcasts) ---
    op.create_table(
        "campaign_recipients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
        # queued | sent | delivered | read | clicked | failed | skipped
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_recipient"),
    )

    # --- opt_in_links (click-to-chat / QR entry points) ---
    op.create_table(
        "opt_in_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        # whatsapp | telegram | instagram
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=True),
        sa.Column("welcome_message", sa.Text, nullable=True),
        # Optional: auto-enroll in drip sequence
        sa.Column("drip_sequence_id", sa.String(36), sa.ForeignKey("drip_sequences.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scan_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("opt_in_links")
    op.drop_table("campaign_recipients")
    op.drop_table("products")
    op.drop_table("drip_enrollments")
    op.drop_table("drip_steps")
    op.drop_table("drip_sequences")
    op.drop_column("campaigns", "failed_count")
    op.drop_column("campaigns", "clicked_count")
    op.drop_column("campaigns", "read_count")
    op.drop_column("campaigns", "delivered_count")
    op.drop_column("campaigns", "sent_count")
    op.drop_column("campaigns", "send_at")
    op.drop_column("campaigns", "channel_id")
    op.drop_column("contacts", "custom_fields")
    op.drop_column("contacts", "notes")
    op.drop_column("contacts", "opt_out_at")
    op.drop_column("contacts", "double_opt_in_confirmed_at")
    op.drop_column("contacts", "double_opt_in_sent_at")
