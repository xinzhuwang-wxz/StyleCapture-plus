"""accounts sessions and deletion tombstones

Revision ID: 20260727_0017
Revises: 20260726_0016
Create Date: 2026-07-27 00:17:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260727_0017"
down_revision = "20260726_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subject_id", name=op.f("pk_accounts")),
    )
    op.create_table(
        "deletion_requests",
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subject_id", name=op.f("pk_deletion_requests")),
    )
    op.create_table(
        "subject_tombstones",
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subject_id", name=op.f("pk_subject_tombstones")),
    )
    op.create_table(
        "external_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("account_subject", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_subject"],
            ["accounts.subject_id"],
            name=op.f("fk_external_identities_account_subject_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_identities")),
        sa.UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_external_identities_provider_subject",
        ),
    )
    op.create_index(
        "ix_external_identities_account_subject",
        "external_identities",
        ["account_subject"],
        unique=False,
    )
    op.create_table(
        "subject_aliases",
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["canonical_subject_id"],
            ["accounts.subject_id"],
            name=op.f("fk_subject_aliases_canonical_subject_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("subject_id", name=op.f("pk_subject_aliases")),
    )
    op.create_table(
        "device_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_subject", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("access_token_hash", sa.String(length=64), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("device_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_subject"],
            ["accounts.subject_id"],
            name=op.f("fk_device_sessions_account_subject_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_device_sessions")),
        sa.UniqueConstraint("refresh_token_hash", name="uq_device_sessions_refresh_token_hash"),
    )
    op.create_index("ix_device_sessions_access_token_hash", "device_sessions", ["access_token_hash"])
    op.create_index("ix_device_sessions_account_subject", "device_sessions", ["account_subject"])
    op.create_index("ix_device_sessions_family_id", "device_sessions", ["family_id"])
    op.create_table(
        "used_refresh_tokens",
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("refresh_token_hash", name=op.f("pk_used_refresh_tokens")),
    )
    op.create_table(
        "apple_authorization_codes",
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("account_subject", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("code_hash", name=op.f("pk_apple_authorization_codes")),
    )


def downgrade() -> None:
    op.drop_table("apple_authorization_codes")
    op.drop_table("used_refresh_tokens")
    op.drop_index("ix_device_sessions_family_id", table_name="device_sessions")
    op.drop_index("ix_device_sessions_account_subject", table_name="device_sessions")
    op.drop_index("ix_device_sessions_access_token_hash", table_name="device_sessions")
    op.drop_table("device_sessions")
    op.drop_table("subject_aliases")
    op.drop_index("ix_external_identities_account_subject", table_name="external_identities")
    op.drop_table("external_identities")
    op.drop_table("subject_tombstones")
    op.drop_table("deletion_requests")
    op.drop_table("accounts")
