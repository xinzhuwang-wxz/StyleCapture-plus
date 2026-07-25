"""Allow provider-native embedding dimensions without discarding existing vectors."""

from __future__ import annotations

from alembic import op
from pgvector.sqlalchemy import Vector

revision = "20260725_0006"
down_revision = "20260725_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "items",
        "embedding",
        existing_type=Vector(768),
        type_=Vector(),
        postgresql_using="embedding::vector",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM items
                WHERE embedding IS NOT NULL
                  AND vector_dims(embedding) <> 768
            ) THEN
                RAISE EXCEPTION
                    'cannot safely downgrade: non-768 provider embeddings exist';
            END IF;
        END
        $$;
        """
    )
    op.alter_column(
        "items",
        "embedding",
        existing_type=Vector(),
        type_=Vector(768),
        postgresql_using="embedding::vector(768)",
    )
