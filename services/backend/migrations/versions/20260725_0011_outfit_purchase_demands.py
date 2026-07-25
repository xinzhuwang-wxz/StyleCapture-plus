"""Persist real search demands for missing outfit slots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0011"
down_revision: str | Sequence[str] | None = "20260725_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outfit_purchase_demands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("look_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("search_query", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('tops','bottoms','dresses','outerwear','shoes','accessories')",
            name="outfit_purchase_demand_role",
        ),
        sa.CheckConstraint(
            "status IN ('wanted','purchased_pending','owned')",
            name="outfit_purchase_demand_status",
        ),
        sa.ForeignKeyConstraint(
            ["look_id"],
            ["looks.id"],
            name="fk_outfit_purchase_demands_look_id_looks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outfit_purchase_demands"),
        sa.UniqueConstraint(
            "look_id",
            "role",
            name="uq_outfit_purchase_demands_look_role",
        ),
    )
    op.create_index(
        "ix_outfit_purchase_demands_user_look",
        "outfit_purchase_demands",
        ["user_id", "look_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outfit_purchase_demands_user_look",
        table_name="outfit_purchase_demands",
    )
    op.drop_table("outfit_purchase_demands")
