from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class AccountDomainError(ValueError):
    """Base class for expected account-domain policy failures."""


class AuthorizationCodeReplayError(AccountDomainError):
    pass


class SubjectDeletedError(AccountDomainError):
    pass


class AccountBindingConflictError(AccountDomainError):
    pass


class ProviderGrantRevocationError(AccountDomainError):
    pass


class RefreshTokenReuseError(AccountDomainError):
    pass


class SessionRevokedError(AccountDomainError):
    pass


class RefreshTokenExpiredError(AccountDomainError):
    pass


class AccessTokenExpiredError(AccountDomainError):
    pass


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("account timestamps must be timezone-aware")
    return value.astimezone(UTC)


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def hash_secret(value: str, pepper: str) -> str:
    return hmac.new(pepper.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_nonce(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


@dataclass(frozen=True, slots=True)
class AppleIdentityClaims:
    issuer: str
    audience: str
    subject: str
    expires_at: datetime
    issued_at: datetime
    nonce: str | None = None
    provider_grant: AppleProviderGrant | None = None


@dataclass(frozen=True, slots=True)
class AppleProviderGrant:
    provider_subject: str
    access_token: str | None
    refresh_token: str | None
    issued_at: datetime

    def revocable_token(self) -> tuple[str, str] | None:
        if self.refresh_token:
            return self.refresh_token, "refresh_token"
        if self.access_token:
            return self.access_token, "access_token"
        return None


@dataclass(frozen=True, slots=True)
class AppleProviderGrantRevocationAttempt:
    grant_id: UUID
    generation: int
    lease_owner: str
    grant: AppleProviderGrant


@dataclass(frozen=True, slots=True)
class AppleProviderGrantRevocationClaim:
    attempt: AppleProviderGrantRevocationAttempt
    lease_owner: str


@dataclass(frozen=True, slots=True)
class Account:
    subject_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    provider: str
    provider_subject: str
    account_subject: UUID
    created_at: datetime


class SessionState(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class DeviceSession:
    id: UUID
    family_id: UUID
    account_subject: str
    refresh_token_hash: str
    access_token_hash: str | None
    access_expires_at: datetime | None
    refresh_expires_at: datetime
    state: SessionState
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None = None
    device_name: str | None = None

    @classmethod
    def create(
        cls,
        *,
        account_subject: str | UUID,
        refresh_token_hash: str,
        now: datetime,
        access_token_hash: str | None = None,
        access_expires_at: datetime | None = None,
        refresh_expires_at: datetime,
        device_name: str | None = None,
    ) -> DeviceSession:
        timestamp = _aware(now)
        return cls(
            id=uuid4(),
            family_id=uuid4(),
            account_subject=str(account_subject),
            refresh_token_hash=refresh_token_hash,
            access_token_hash=access_token_hash,
            access_expires_at=_aware(access_expires_at) if access_expires_at else None,
            refresh_expires_at=_aware(refresh_expires_at),
            state=SessionState.ACTIVE,
            created_at=timestamp,
            updated_at=timestamp,
            device_name=device_name,
        )

    def rotate(
        self,
        *,
        refresh_token_hash: str,
        access_token_hash: str,
        access_expires_at: datetime,
        now: datetime,
    ) -> DeviceSession:
        self.assert_refresh_active(now=now)
        return DeviceSession(
            id=self.id,
            family_id=self.family_id,
            account_subject=self.account_subject,
            refresh_token_hash=refresh_token_hash,
            access_token_hash=access_token_hash,
            access_expires_at=_aware(access_expires_at),
            refresh_expires_at=self.refresh_expires_at,
            state=SessionState.ACTIVE,
            created_at=self.created_at,
            updated_at=_aware(now),
            device_name=self.device_name,
        )

    def revoke(self, now: datetime) -> DeviceSession:
        timestamp = _aware(now)
        return DeviceSession(
            id=self.id,
            family_id=self.family_id,
            account_subject=self.account_subject,
            refresh_token_hash=self.refresh_token_hash,
            access_token_hash=self.access_token_hash,
            access_expires_at=self.access_expires_at,
            refresh_expires_at=self.refresh_expires_at,
            state=SessionState.REVOKED,
            created_at=self.created_at,
            updated_at=timestamp,
            revoked_at=timestamp,
            device_name=self.device_name,
        )

    def assert_refresh_active(self, *, now: datetime) -> None:
        if self.state is SessionState.REVOKED:
            raise SessionRevokedError("session revoked")
        if _aware(now) >= self.refresh_expires_at:
            raise RefreshTokenExpiredError("refresh token expired")

    def assert_access_active(self, *, now: datetime) -> None:
        self.assert_refresh_active(now=now)
        if self.access_expires_at is not None and _aware(now) >= self.access_expires_at:
            raise AccessTokenExpiredError("access token expired")


@dataclass(frozen=True, slots=True)
class SubjectTombstone:
    subject_id: UUID
    reason: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DeletionRequest:
    subject_id: UUID
    status: str
    requested_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AccountDeletionAcceptance:
    deletion: DeletionRequest
    apple_revocation_attempt: AppleProviderGrantRevocationAttempt | None = None


@dataclass(frozen=True, slots=True)
class AuthTokens:
    account_subject: UUID
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    token_type: str = "Bearer"
