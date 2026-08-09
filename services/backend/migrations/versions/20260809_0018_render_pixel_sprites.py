"""Store transparent sprites alongside pixel-cover cards.

Revision ID: 20260809_0018
Revises: 20260808_0017
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "20260809_0018"
down_revision = "20260808_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("render_artifacts", sa.Column("sprite_object_key", sa.String(512)))
    op.add_column("render_artifacts", sa.Column("sprite_content_hash", sa.String(64)))
    op.add_column("render_artifacts", sa.Column("sprite_content_type", sa.String(80)))
    op.create_check_constraint(
        "render_artifact_sprite_complete",
        "render_artifacts",
        "(sprite_object_key IS NULL AND sprite_content_hash IS NULL AND sprite_content_type IS NULL) "
        "OR (kind = 'pixel_cover' AND status = 'succeeded' AND sprite_object_key IS NOT NULL "
        "AND sprite_content_hash IS NOT NULL AND sprite_content_type = 'image/png')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "render_artifact_sprite_complete", "render_artifacts", type_="check"
    )
    op.drop_column("render_artifacts", "sprite_content_type")
    op.drop_column("render_artifacts", "sprite_content_hash")
    op.drop_column("render_artifacts", "sprite_object_key")
