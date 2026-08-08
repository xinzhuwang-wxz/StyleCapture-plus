"""Persist transparent sprite derivatives for pixel trials."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260808_0017"
down_revision = "20260726_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pixel_trials", sa.Column("sprite_object_key", sa.String(512)))
    op.add_column("pixel_trials", sa.Column("sprite_content_hash", sa.String(64)))
    op.add_column("pixel_trials", sa.Column("sprite_content_type", sa.String(80)))
    op.create_check_constraint(
        "pixel_trial_sprite_output_complete",
        "pixel_trials",
        "(sprite_object_key IS NULL AND sprite_content_hash IS NULL "
        "AND sprite_content_type IS NULL) OR "
        "(sprite_object_key IS NOT NULL AND sprite_content_hash IS NOT NULL "
        "AND sprite_content_type IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "pixel_trial_sprite_output_complete",
        "pixel_trials",
        type_="check",
    )
    op.drop_column("pixel_trials", "sprite_content_type")
    op.drop_column("pixel_trials", "sprite_content_hash")
    op.drop_column("pixel_trials", "sprite_object_key")
