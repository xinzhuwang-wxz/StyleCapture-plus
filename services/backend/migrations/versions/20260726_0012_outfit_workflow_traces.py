"""Persist sanitized, user-queryable outfit workflow traces."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0012"
down_revision: str | Sequence[str] | None = "20260725_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outfit_workflow_traces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("explanation_state", sa.String(length=32), nullable=False),
        sa.Column("plan_count", sa.Integer(), nullable=False),
        sa.Column("capability_alias", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('candidates_ready','completed','degraded')",
            name="outfit_workflow_trace_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outfit_workflow_traces"),
        sa.UniqueConstraint(
            "user_id",
            "request_id",
            name="uq_outfit_workflow_traces_user_request",
        ),
    )
    op.create_index(
        "ix_outfit_workflow_traces_user_updated",
        "outfit_workflow_traces",
        ["user_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outfit_workflow_traces_user_updated",
        table_name="outfit_workflow_traces",
    )
    op.drop_table("outfit_workflow_traces")
