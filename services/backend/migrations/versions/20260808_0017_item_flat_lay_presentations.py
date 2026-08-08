"""Allow deterministic real-item flat-lay presentations.

Revision ID: 20260808_0017
Revises: 20260726_0016
Create Date: 2026-08-08
"""

from alembic import op


revision = "20260808_0017"
down_revision = "20260726_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "item_presentation_kind",
        "item_presentation_assets",
        type_="check",
    )
    op.create_check_constraint(
        "item_presentation_kind",
        "item_presentation_assets",
        "kind IN ('pixel_item','flat_lay_item')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "item_presentation_kind",
        "item_presentation_assets",
        type_="check",
    )
    op.create_check_constraint(
        "item_presentation_kind",
        "item_presentation_assets",
        "kind IN ('pixel_item')",
    )
