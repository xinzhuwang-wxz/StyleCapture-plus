"""Persist saved Looks, component-to-Item relations, and preference events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260725_0007"
down_revision: str | Sequence[str] | None = "20260725_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "looks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("capture_id", sa.Uuid(), nullable=False),
        sa.Column("source_selection_key", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "analysis",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("display_object_key", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('feed_saved','user_created','ai_generated')",
            name="look_source",
        ),
        sa.CheckConstraint(
            "status IN ('processing','partial','ready','error')",
            name="look_status",
        ),
        sa.ForeignKeyConstraint(
            ["capture_id"],
            ["captures.id"],
            name="fk_looks_capture_id_captures",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_looks"),
        sa.UniqueConstraint(
            "capture_id",
            "source_selection_key",
            name="uq_looks_capture_id_source_selection_key",
        ),
    )
    op.create_index("ix_looks_user_created", "looks", ["user_id", "created_at"])
    op.create_index("ix_looks_user_status", "looks", ["user_id", "status"])

    op.create_table(
        "look_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("look_id", sa.Uuid(), nullable=False),
        sa.Column("component_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=True),
        sa.Column(
            "evidence_region",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("layer", sa.String(length=80), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "grounding_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','processing','ready','error')",
            name="look_component_status",
        ),
        sa.CheckConstraint(
            "(status = 'ready' AND item_id IS NOT NULL) OR (status <> 'ready' AND item_id IS NULL)",
            name="look_component_ready_item",
        ),
        sa.CheckConstraint(
            "display_order >= 0",
            name="look_component_display_order",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="look_component_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name="fk_look_components_item_id_items",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["look_id"],
            ["looks.id"],
            name="fk_look_components_look_id_looks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_look_components"),
        sa.UniqueConstraint(
            "look_id",
            "component_key",
            name="uq_look_components_look_id_component_key",
        ),
    )
    op.create_index(
        "ix_look_components_look_order",
        "look_components",
        ["look_id", "display_order"],
    )
    op.create_index(
        "ix_look_components_look_item",
        "look_components",
        ["look_id", "item_id"],
        unique=True,
        postgresql_where=sa.text("item_id IS NOT NULL"),
    )

    op.create_table(
        "preference_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("look_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('look_saved','liking_reason_added')",
            name="preference_signal_kind",
        ),
        sa.ForeignKeyConstraint(
            ["look_id"],
            ["looks.id"],
            name="fk_preference_signals_look_id_looks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_preference_signals"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_preference_signals_user_id_idempotency_key",
        ),
    )
    op.create_index(
        "ix_preference_signals_user_created",
        "preference_signals",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_preference_signals_look_created",
        "preference_signals",
        ["look_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_preference_signals_look_created",
        table_name="preference_signals",
    )
    op.drop_index(
        "ix_preference_signals_user_created",
        table_name="preference_signals",
    )
    op.drop_table("preference_signals")
    op.drop_index("ix_look_components_look_item", table_name="look_components")
    op.drop_index("ix_look_components_look_order", table_name="look_components")
    op.drop_table("look_components")
    op.drop_index("ix_looks_user_status", table_name="looks")
    op.drop_index("ix_looks_user_created", table_name="looks")
    op.drop_table("looks")
