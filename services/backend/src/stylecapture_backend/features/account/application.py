from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from stylecapture_backend.features.account.domain import (
    AccessTokenExpiredError,
    Account,
    AccountBindingConflictError,
    AppleProviderGrantRevocationAttempt,
    AuthorizationCodeReplayError,
    AuthTokens,
    DeletionRequest,
    DeviceSession,
    ExternalIdentity,
    ProviderGrantRevocationError,
    RefreshTokenExpiredError,
    RefreshTokenReuseError,
    SessionRevokedError,
    SubjectDeletedError,
    constant_time_equal,
    hash_nonce,
    hash_secret,
    new_token,
)
from stylecapture_backend.features.account.ports import (
    AccountRepository,
    AppleIdentityVerifier,
    AppleProviderGrantRepository,
    AppleProviderGrantRevoker,
)


class AccountError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class AuthenticateWithAppleCommand:
    anonymous_subject: UUID
    identity_token: str
    authorization_code: str
    nonce: str
    device_name: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshSessionCommand:
    refresh_token: str


@dataclass(frozen=True, slots=True)
class AccountDeletionCommand:
    access_token: str
    idempotency_key: str


class AccountApplication:
    def __init__(
        self,
        *,
        repository: AccountRepository,
        apple_identity: AppleIdentityVerifier,
        allowed_audiences: frozenset[str],
        token_secret: str,
        apple_provider_grants: AppleProviderGrantRepository | None = None,
        apple_provider_revoker: AppleProviderGrantRevoker | None = None,
        now: Callable[[], datetime] | None = None,
        access_lifetime: timedelta = timedelta(minutes=15),
        refresh_lifetime: timedelta = timedelta(days=30),
    ) -> None:
        if len(token_secret) < 24:
            raise ValueError("account token secret must be at least 24 characters")
        self._repository = repository
        self._apple_identity = apple_identity
        self._apple_provider_grants = apple_provider_grants
        self._apple_provider_revoker = apple_provider_revoker
        self._allowed_audiences = allowed_audiences
        self._token_secret = token_secret
        self._now = now or (lambda: datetime.now(UTC))
        self._access_lifetime = access_lifetime
        self._refresh_lifetime = refresh_lifetime

    async def authenticate_with_apple(self, command: AuthenticateWithAppleCommand) -> AuthTokens:
        claims = await self._apple_identity.verify(
            command.identity_token,
            command.authorization_code,
        )
        if claims.audience not in self._allowed_audiences:
            raise AccountError("apple_audience_invalid", "Apple identity audience is not allowed")
        expected_nonce = hash_nonce(command.nonce)
        if claims.nonce is None or not constant_time_equal(claims.nonce, expected_nonce):
            raise AccountError("apple_nonce_invalid", "Apple identity nonce did not match")
        now = self._aware_now()
        account_subject = uuid5(NAMESPACE_URL, f"stylecapture:apple:{claims.subject}")
        account = Account(subject_id=account_subject, created_at=now)
        identity = ExternalIdentity(
            provider="apple",
            provider_subject=claims.subject,
            account_subject=account_subject,
            created_at=now,
        )
        try:
            account = await self._repository.bind_apple_identity(
                anonymous_subject=command.anonymous_subject,
                identity=identity,
                authorization_code_hash=self._hash(command.authorization_code),
                account=account,
                apple_provider_grant=claims.provider_grant,
            )
        except AuthorizationCodeReplayError as error:
            raise AccountError(
                "authorization_code_replayed",
                "Apple authorization code was replayed",
            ) from error
        except SubjectDeletedError as error:
            raise AccountError("account_deleted", "Account has been deleted") from error
        except AccountBindingConflictError as error:
            raise AccountError(
                "account_binding_conflict",
                "Account is already bound to a different Apple identity",
            ) from error
        return await self._issue_session(account.subject_id, device_name=command.device_name)

    async def refresh_session(self, command: RefreshSessionCommand) -> AuthTokens:
        refresh_hash = self._hash(command.refresh_token)
        session = await self._repository.find_by_refresh_hash(refresh_hash)
        if session is None:
            raise AccountError("refresh_token_reused", "refresh token reuse detected")
        now = self._aware_now()
        try:
            session.assert_refresh_active(now=now)
        except RefreshTokenExpiredError as error:
            raise AccountError("refresh_token_expired", str(error)) from error
        except SessionRevokedError as error:
            raise AccountError("session_revoked", str(error)) from error
        access_token = new_token()
        refresh_token = new_token()
        access_expires_at = now + self._access_lifetime
        rotated = session.rotate(
            refresh_token_hash=self._hash(refresh_token),
            access_token_hash=self._hash(access_token),
            access_expires_at=access_expires_at,
            now=now,
        )
        try:
            await self._repository.rotate_session(
                session_id=session.id,
                old_refresh_token_hash=refresh_hash,
                rotated=rotated,
            )
        except RefreshTokenReuseError as error:
            await self._repository.revoke_session_family(session.family_id)
            raise AccountError("refresh_token_reused", "refresh token reuse detected") from error
        return AuthTokens(
            account_subject=UUID(session.account_subject),
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires_at,
        )

    async def resolve_access_token(self, access_token: str) -> UUID:
        session = await self._repository.find_by_access_hash(self._hash(access_token))
        if session is None:
            raise AccountError("session_invalid", "Session is invalid")
        try:
            session.assert_access_active(now=self._aware_now())
        except (AccessTokenExpiredError, RefreshTokenExpiredError, SessionRevokedError) as error:
            raise AccountError("session_invalid", str(error)) from error
        subject = await self._repository.resolve_subject(UUID(session.account_subject))
        await self._repository.assert_can_write(subject)
        return subject

    async def resolve_cookie_subject(self, subject_id: UUID) -> UUID:
        subject = await self._repository.resolve_subject(subject_id)
        await self._repository.assert_can_write(subject)
        return subject

    async def resolve_subject(self, subject_id: UUID) -> UUID:
        return await self._repository.resolve_subject(subject_id)

    async def request_account_deletion(self, subject_id: UUID) -> DeletionRequest:
        return (
            await self._repository.accept_account_deletion(
                subject_id,
                reason="account_deletion",
            )
        ).deletion

    async def request_account_deletion_with_access_token(
        self,
        command: AccountDeletionCommand,
    ) -> DeletionRequest:
        access_hash = self._hash(command.access_token)
        key_hash = self._hash(command.idempotency_key)
        try:
            subject_id = await self.resolve_access_token(command.access_token)
        except AccountError:
            replay = await self._repository.deletion_request_for_idempotency(
                access_token_hash=access_hash,
                idempotency_key_hash=key_hash,
            )
            if replay is None:
                raise
            return replay
        try:
            return (
                await self._repository.accept_account_deletion(
                    subject_id,
                    reason="account_deletion",
                    access_token_hash=access_hash,
                    idempotency_key_hash=key_hash,
                )
            ).deletion
        except AccountBindingConflictError as error:
            raise AccountError(
                "account_delete_conflict",
                "Account deletion idempotency key conflicts with another credential",
            ) from error

    async def process_apple_provider_revocations(
        self,
        *,
        lease_owner: str | None = None,
        limit: int = 25,
    ) -> int:
        if self._apple_provider_grants is None:
            return 0
        claims = await self._apple_provider_grants.claim_apple_provider_revocations(
            lease_owner=lease_owner or f"account-revoker-{uuid4()}",
            limit=limit,
        )
        for claim in claims:
            await self._revoke_apple_provider_grant(claim.attempt)
        return len(claims)

    async def _issue_session(self, account_subject: UUID, *, device_name: str | None) -> AuthTokens:
        access_token = new_token()
        refresh_token = new_token()
        now = self._aware_now()
        access_expires_at = now + self._access_lifetime
        session = DeviceSession.create(
            account_subject=account_subject,
            refresh_token_hash=self._hash(refresh_token),
            access_token_hash=self._hash(access_token),
            access_expires_at=access_expires_at,
            refresh_expires_at=now + self._refresh_lifetime,
            now=now,
            device_name=device_name,
        )
        await self._repository.save_session(session)
        return AuthTokens(
            account_subject=account_subject,
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires_at,
        )

    def _hash(self, value: str) -> str:
        return hash_secret(value, self._token_secret)

    async def _revoke_apple_provider_grant(
        self,
        attempt: AppleProviderGrantRevocationAttempt | None,
    ) -> None:
        if attempt is None or self._apple_provider_grants is None:
            return
        token = attempt.grant.revocable_token()
        if token is None:
            await self._apple_provider_grants.mark_apple_provider_revoked(attempt)
            return
        if self._apple_provider_revoker is None:
            return
        token_value, token_type_hint = token
        try:
            await self._apple_provider_revoker.revoke(
                token=token_value,
                token_type_hint=token_type_hint,
            )
        except ProviderGrantRevocationError:
            await self._apple_provider_grants.mark_apple_provider_revocation_failed(
                attempt,
                failure_code="apple_revocation_failed",
            )
            return
        await self._apple_provider_grants.mark_apple_provider_revoked(attempt)

    def _aware_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise RuntimeError("account clock must return timezone-aware datetime")
        return value.astimezone(UTC)
