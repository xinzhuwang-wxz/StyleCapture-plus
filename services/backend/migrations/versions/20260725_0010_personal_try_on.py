"""Store the private user photo selected for a personal try-on render."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0010"
down_revision: str | Sequence[str] | None = "20260725_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "render_artifacts",
        sa.Column("subject_object_key", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("render_artifacts", "subject_object_key")
