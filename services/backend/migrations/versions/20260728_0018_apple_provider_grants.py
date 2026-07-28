"""apple provider grants for revocation

Revision ID: 20260728_0018
Revises: 20260727_0017
Create Date: 2026-07-28 00:18:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260728_0018"
down_revision = "20260727_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "apple_provider_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("account_subject", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("encrypted_access_token", sa.String(length=4096), nullable=True),
        sa.Column("encrypted_refresh_token", sa.String(length=4096), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_status", sa.String(length=32), nullable=False),
        sa.Column("revocation_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_failure_code", sa.String(length=80), nullable=True),
        sa.Column("revocation_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revocation_lease_owner", sa.String(length=120), nullable=True),
        sa.Column("revocation_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_subject"],
            ["accounts.subject_id"],
            name=op.f("fk_apple_provider_grants_account_subject_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_apple_provider_grants")),
    )
    op.create_index(
        "ix_apple_provider_grants_account_subject",
        "apple_provider_grants",
        ["account_subject"],
        unique=False,
    )
    op.create_index(
        "ix_apple_provider_grants_revocation_claim",
        "apple_provider_grants",
        ["revocation_status", "revocation_lease_expires_at"],
        unique=False,
    )
    op.create_table(
        "account_deletion_idempotency",
        sa.Column("idempotency_key_hash", sa.String(length=128), nullable=False),
        sa.Column("access_token_hash", sa.String(length=128), nullable=False),
        sa.Column("account_subject", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deletion_subject", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_subject"],
            ["accounts.subject_id"],
            name=op.f("fk_account_deletion_idempotency_account_subject_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deletion_subject"],
            ["deletion_requests.subject_id"],
            name=op.f("fk_account_deletion_idempotency_deletion_subject_deletion_requests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "idempotency_key_hash",
            name=op.f("pk_account_deletion_idempotency"),
        ),
    )
    op.create_index(
        "ix_account_deletion_idempotency_access",
        "account_deletion_idempotency",
        ["access_token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_deletion_idempotency_access",
        table_name="account_deletion_idempotency",
    )
    op.drop_table("account_deletion_idempotency")
    op.drop_index(
        "ix_apple_provider_grants_revocation_claim",
        table_name="apple_provider_grants",
    )
    op.drop_index(
        "ix_apple_provider_grants_account_subject",
        table_name="apple_provider_grants",
    )
    op.drop_table("apple_provider_grants")
