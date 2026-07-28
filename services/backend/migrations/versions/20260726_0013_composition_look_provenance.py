"""Represent AI-composed Looks without fabricated single-frame provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0013"
down_revision: str | Sequence[str] | None = "20260726_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("looks", "capture_id", existing_type=sa.Uuid(), nullable=True)
    op.execute(
        """
        UPDATE look_components AS component
        SET evidence_region = '[]'::jsonb,
            confidence = 0,
            grounding_metadata = component.grounding_metadata || jsonb_build_object(
                'evidence_type', 'composition_item_reference',
                'item_id', item.id::text,
                'item_capture_id', item.capture_id::text,
                'item_source_object_key', item.source_object_key,
                'item_display_object_key', item.display_object_key,
                'item_selection_key', item.selection_key,
                'item_version', item.updated_at::text
            )
        FROM looks AS look, items AS item
        WHERE component.look_id = look.id
          AND component.item_id = item.id
          AND look.source = 'ai_generated'
        """
    )
    op.execute("UPDATE looks SET capture_id = NULL WHERE source = 'ai_generated'")
    op.create_check_constraint(
        "look_source_capture_provenance",
        "looks",
        "(source = 'ai_generated' AND capture_id IS NULL) OR "
        "(source <> 'ai_generated' AND capture_id IS NOT NULL)",
    )
    op.create_index(
        "uq_looks_composition_user_source_selection",
        "looks",
        ["user_id", "source", "source_selection_key"],
        unique=True,
        postgresql_where=sa.text("capture_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_looks_composition_user_source_selection",
        table_name="looks",
    )
    op.drop_constraint(
        "look_source_capture_provenance",
        "looks",
        type_="check",
    )
    op.execute("DELETE FROM looks WHERE source = 'ai_generated' AND capture_id IS NULL")
    op.alter_column("looks", "capture_id", existing_type=sa.Uuid(), nullable=False)
