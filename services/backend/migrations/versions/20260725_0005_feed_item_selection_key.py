"""Allow one stable wardrobe item per Feed selection."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260725_0005"
down_revision = "20260725_0004"
branch_labels = None
depends_on = None

WHOLE_CAPTURE_SELECTION_KEY = "whole_capture"


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column(
            "selection_key",
            sa.String(length=64),
            nullable=False,
            server_default=WHOLE_CAPTURE_SELECTION_KEY,
        ),
    )
    op.drop_constraint("uq_items_capture_id", "items", type_="unique")
    op.create_unique_constraint(
        "uq_items_capture_id_selection_key",
        "items",
        ["capture_id", "selection_key"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM items
                GROUP BY capture_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'cannot safely downgrade: a capture owns multiple selection items';
            END IF;
        END
        $$;
        """
    )
    op.drop_constraint(
        "uq_items_capture_id_selection_key",
        "items",
        type_="unique",
    )
    op.create_unique_constraint("uq_items_capture_id", "items", ["capture_id"])
    op.drop_column("items", "selection_key")
