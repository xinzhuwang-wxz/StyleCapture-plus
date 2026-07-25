"""Persist ephemeral photo-to-pixel trial tasks."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260726_0015"
down_revision = "20260726_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pixel_trials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("subject_object_key", sa.String(length=512), nullable=True),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("content_type", sa.String(length=80), nullable=True),
        sa.Column("subject_attached", sa.Boolean(), nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_message", sa.String(length=1000), nullable=True),
        sa.Column("provider_trace", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed')",
            name="pixel_trial_status",
        ),
        sa.CheckConstraint(
            "(status = 'succeeded' AND object_key IS NOT NULL AND content_hash IS NOT NULL "
            "AND content_type IS NOT NULL) OR "
            "(status <> 'succeeded' AND object_key IS NULL AND content_hash IS NULL "
            "AND content_type IS NULL)",
            name="pixel_trial_output_status",
        ),
        sa.CheckConstraint(
            "status = 'failed' OR failure_code IS NULL",
            name="pixel_trial_failure_code_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pixel_trials"),
    )
    op.create_index("ix_pixel_trials_user_created", "pixel_trials", ["user_id", "created_at"])
    op.create_index(
        "ix_pixel_trials_user_request_key",
        "pixel_trials",
        ["user_id", "request_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_pixel_trials_user_request_key", table_name="pixel_trials")
    op.drop_index("ix_pixel_trials_user_created", table_name="pixel_trials")
    op.drop_table("pixel_trials")
