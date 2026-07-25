"""Persist RenderArtifact state, outputs, fallback links, and private provider trace."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260725_0009"
down_revision: str | Sequence[str] | None = "20260725_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "render_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("look_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("input_version", sa.String(length=80), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("privacy", sa.String(length=32), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("content_type", sa.String(length=80), nullable=True),
        sa.Column("share_eligible", sa.Boolean(), nullable=False),
        sa.Column("source_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("fallback_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_message", sa.String(length=1000), nullable=True),
        sa.Column(
            "provider_trace",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('collage','try_on','pixel_cover')",
            name="render_artifact_kind",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','degraded')",
            name="render_artifact_status",
        ),
        sa.CheckConstraint(
            "privacy IN ('private','shareable_pixel')",
            name="render_artifact_privacy",
        ),
        sa.CheckConstraint(
            "(status IN ('succeeded','degraded') AND object_key IS NOT NULL AND content_hash IS NOT NULL "
            "AND content_type IS NOT NULL) OR "
            "(status NOT IN ('succeeded','degraded') AND object_key IS NULL AND content_hash IS NULL "
            "AND content_type IS NULL)",
            name="render_artifact_output_status",
        ),
        sa.CheckConstraint(
            "status <> 'degraded' OR fallback_artifact_id IS NOT NULL",
            name="render_artifact_degraded_fallback",
        ),
        sa.CheckConstraint(
            "privacy <> 'shareable_pixel' OR kind = 'pixel_cover'",
            name="render_artifact_shareable_pixel_kind",
        ),
        sa.ForeignKeyConstraint(
            ["look_id"],
            ["looks.id"],
            name="fk_render_artifacts_look_id_looks",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            ["render_artifacts.id"],
            name="fk_render_artifacts_source_artifact_id_render_artifacts",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fallback_artifact_id"],
            ["render_artifacts.id"],
            name="fk_render_artifacts_fallback_artifact_id_render_artifacts",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_render_artifacts"),
    )
    op.create_index(
        "ix_render_artifacts_look_created",
        "render_artifacts",
        ["look_id", "created_at"],
    )
    op.create_index(
        "ix_render_artifacts_user_request_key",
        "render_artifacts",
        ["user_id", "request_key"],
        unique=True,
    )
    op.create_index(
        "ix_render_artifacts_cache_hit",
        "render_artifacts",
        ["look_id", "kind", "input_version", "input_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'succeeded' AND object_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_render_artifacts_cache_hit", table_name="render_artifacts")
    op.drop_index("ix_render_artifacts_user_request_key", table_name="render_artifacts")
    op.drop_index("ix_render_artifacts_look_created", table_name="render_artifacts")
    op.drop_table("render_artifacts")
