"""Persist source deletion so retry and display remain honest after refresh."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260725_0002"
down_revision = "20260725_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column(
            "source_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.alter_column("items", "source_available", server_default=None)


def downgrade() -> None:
    op.drop_column("items", "source_available")
