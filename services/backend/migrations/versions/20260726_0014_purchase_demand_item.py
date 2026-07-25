"""Link purchase demands to real wardrobe assets when one exists."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0014"
down_revision: str | Sequence[str] | None = "20260726_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outfit_purchase_demands",
        sa.Column("item_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_outfit_purchase_demands_item_id_items",
        "outfit_purchase_demands",
        "items",
        ["item_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_outfit_purchase_demands_item_id_items",
        "outfit_purchase_demands",
        type_="foreignkey",
    )
    op.drop_column("outfit_purchase_demands", "item_id")
