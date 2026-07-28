from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from stylecapture_backend.platform.database import Base


class AccountRecord(Base):
    __tablename__ = "accounts"

    subject_id: Mapped[UUID] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExternalIdentityRecord(Base):
    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_subject", name="uq_external_identities_provider_subject"
        ),
        Index("ix_external_identities_account_subject", "account_subject"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    account_subject: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.subject_id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SubjectAliasRecord(Base):
    __tablename__ = "subject_aliases"

    subject_id: Mapped[UUID] = mapped_column(primary_key=True)
    canonical_subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.subject_id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DeviceSessionRecord(Base):
    __tablename__ = "device_sessions"
    __table_args__ = (
        UniqueConstraint("refresh_token_hash", name="uq_device_sessions_refresh_token_hash"),
        Index("ix_device_sessions_access_token_hash", "access_token_hash"),
        Index("ix_device_sessions_family_id", "family_id"),
        Index("ix_device_sessions_account_subject", "account_subject"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    family_id: Mapped[UUID] = mapped_column(nullable=False)
    account_subject: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.subject_id", ondelete="CASCADE"),
        nullable=False,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    access_token_hash: Mapped[str | None] = mapped_column(String(64))
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsedRefreshTokenRecord(Base):
    __tablename__ = "used_refresh_tokens"

    refresh_token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    family_id: Mapped[UUID] = mapped_column(nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AppleAuthorizationCodeRecord(Base):
    __tablename__ = "apple_authorization_codes"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_subject: Mapped[UUID] = mapped_column(nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SubjectTombstoneRecord(Base):
    __tablename__ = "subject_tombstones"

    subject_id: Mapped[UUID] = mapped_column(primary_key=True)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DeletionRequestRecord(Base):
    __tablename__ = "deletion_requests"

    subject_id: Mapped[UUID] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
