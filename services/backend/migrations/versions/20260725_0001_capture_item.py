"""Create immutable captures, durable processing jobs, and canonical items."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260725_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "captures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("ownership", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_kind IN ('upload','camera','feed')",
            name="capture_source_kind",
        ),
        sa.CheckConstraint(
            "ownership IN ('owned','inspiration')",
            name="capture_ownership",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_captures"),
        sa.UniqueConstraint("object_key", name="uq_captures_object_key"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_captures_user_id_idempotency_key",
        ),
    )
    op.create_index("ix_captures_user_created", "captures", ["user_id", "created_at"])
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("capture_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('queued','processing','partial','ready','error')",
            name="processing_job_state",
        ),
        sa.ForeignKeyConstraint(
            ["capture_id"],
            ["captures.id"],
            name="fk_processing_jobs_capture_id_captures",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_processing_jobs"),
        sa.UniqueConstraint("capture_id", name="uq_processing_jobs_capture_id"),
    )
    op.create_index(
        "ix_processing_jobs_state_updated",
        "processing_jobs",
        ["state", "updated_at"],
    )
    op.create_table(
        "items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("capture_id", sa.Uuid(), nullable=False),
        sa.Column("source_object_key", sa.String(length=512), nullable=False),
        sa.Column("ownership", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("subcategory", sa.String(length=120), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "model_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ownership IN ('owned','inspiration')",
            name="item_ownership",
        ),
        sa.CheckConstraint(
            "status IN ('processing','partial','ready','error')",
            name="item_status",
        ),
        sa.ForeignKeyConstraint(
            ["capture_id"],
            ["captures.id"],
            name="fk_items_capture_id_captures",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_items"),
        sa.UniqueConstraint("capture_id", name="uq_items_capture_id"),
    )
    op.create_index("ix_items_user_created", "items", ["user_id", "created_at"])
    op.create_index("ix_items_user_status", "items", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_items_user_status", table_name="items")
    op.drop_index("ix_items_user_created", table_name="items")
    op.drop_table("items")
    op.drop_index("ix_processing_jobs_state_updated", table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index("ix_captures_user_created", table_name="captures")
    op.drop_table("captures")
