"""Persist Feed origin, frame metadata, and normalized selection paths."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260725_0003"
down_revision = "20260725_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "captures",
        sa.Column("origin_ref", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "captures",
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("captures", "source_metadata", server_default=None)


def downgrade() -> None:
    op.drop_column("captures", "source_metadata")
    op.drop_column("captures", "origin_ref")
