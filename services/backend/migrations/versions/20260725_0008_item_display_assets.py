"""Store derived wardrobe display assets separately from source evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0008"
down_revision: str | Sequence[str] | None = "20260725_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column("display_object_key", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("items", "display_object_key")
