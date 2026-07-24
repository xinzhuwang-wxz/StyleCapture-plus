"""Preserve upload compatibility for capture source metadata."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260725_0004"
down_revision = "20260725_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "captures",
        "source_metadata",
        server_default=sa.text("'{}'::jsonb"),
    )


def downgrade() -> None:
    op.alter_column("captures", "source_metadata", server_default=None)
