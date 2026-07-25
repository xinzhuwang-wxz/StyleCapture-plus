"""Persist generated item presentation assets."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260726_0016"
down_revision = "20260726_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_presentation_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("input_version", sa.String(length=80), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("content_type", sa.String(length=80), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_message", sa.String(length=1000), nullable=True),
        sa.Column("provider_trace", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('pixel_item')", name="item_presentation_kind"),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed')",
            name="item_presentation_status",
        ),
        sa.CheckConstraint(
            "(status = 'succeeded' AND object_key IS NOT NULL AND content_hash IS NOT NULL "
            "AND content_type IS NOT NULL) OR "
            "(status <> 'succeeded' AND object_key IS NULL AND content_hash IS NULL "
            "AND content_type IS NULL)",
            name="item_presentation_output_status",
        ),
        sa.CheckConstraint(
            "status = 'failed' OR failure_code IS NULL",
            name="item_presentation_failure_code_status",
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_item_presentation_assets"),
    )
    op.create_index(
        "ix_item_presentations_user_item",
        "item_presentation_assets",
        ["user_id", "item_id"],
    )
    op.create_index(
        "ix_item_presentations_user_request_key",
        "item_presentation_assets",
        ["user_id", "request_key"],
        unique=True,
    )
    op.create_index(
        "ix_item_presentations_current",
        "item_presentation_assets",
        ["user_id", "item_id", "kind", "input_version", "input_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_item_presentations_current", table_name="item_presentation_assets")
    op.drop_index("ix_item_presentations_user_request_key", table_name="item_presentation_assets")
    op.drop_index("ix_item_presentations_user_item", table_name="item_presentation_assets")
    op.drop_table("item_presentation_assets")
