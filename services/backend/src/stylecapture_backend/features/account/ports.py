from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.account.domain import (
    Account,
    AccountDeletionAcceptance,
    AppleIdentityClaims,
    AppleProviderGrant,
    AppleProviderGrantRevocationAttempt,
    AppleProviderGrantRevocationClaim,
    DeletionRequest,
    DeviceSession,
    ExternalIdentity,
)

ACCOUNT_REVOCATION_SWEEP_TASK_NAME = "stylecapture.account.apple_provider_revocation_sweep"


class AppleIdentityVerifier(Protocol):
    async def verify(
        self,
        identity_token: str,
        authorization_code: str,
    ) -> AppleIdentityClaims: ...


class AppleProviderGrantRevoker(Protocol):
    async def revoke(self, *, token: str, token_type_hint: str) -> None: ...


class AppleProviderGrantRepository(Protocol):
    async def claim_apple_provider_revocations(
        self,
        *,
        lease_owner: str,
        limit: int,
    ) -> list[AppleProviderGrantRevocationClaim]: ...

    async def mark_apple_provider_revoked(
        self,
        attempt: AppleProviderGrantRevocationAttempt,
    ) -> None: ...

    async def mark_apple_provider_revocation_failed(
        self,
        attempt: AppleProviderGrantRevocationAttempt,
        *,
        failure_code: str,
    ) -> None: ...


class SubjectWriteLease(Protocol):
    def subject_write(self, subject_id: UUID) -> AbstractAsyncContextManager[UUID]: ...


class SubjectResolver(Protocol):
    async def resolve_subject(self, subject_id: UUID) -> UUID: ...


class AccountRepository(SubjectWriteLease, SubjectResolver, Protocol):
    async def assert_can_write(self, subject_id: UUID) -> None: ...

    async def bind_apple_identity(
        self,
        *,
        anonymous_subject: UUID,
        identity: ExternalIdentity,
        authorization_code_hash: str,
        account: Account,
        apple_provider_grant: AppleProviderGrant | None = None,
    ) -> Account: ...

    async def save_session(self, session: DeviceSession) -> None: ...

    async def rotate_session(
        self,
        *,
        session_id: UUID,
        old_refresh_token_hash: str,
        rotated: DeviceSession,
    ) -> None: ...

    async def find_by_refresh_hash(self, refresh_token_hash: str) -> DeviceSession | None: ...

    async def find_by_access_hash(self, access_token_hash: str) -> DeviceSession | None: ...

    async def revoke_session_family(self, family_id: UUID) -> None: ...

    async def revoke_subject_sessions(self, subject_id: UUID) -> None: ...

    async def tombstone_subject(self, subject_id: UUID, *, reason: str) -> DeletionRequest: ...

    async def accept_account_deletion(
        self,
        subject_id: UUID,
        *,
        reason: str,
        access_token_hash: str | None = None,
        idempotency_key_hash: str | None = None,
    ) -> AccountDeletionAcceptance: ...

    async def deletion_request_for_idempotency(
        self,
        *,
        access_token_hash: str,
        idempotency_key_hash: str,
    ) -> DeletionRequest | None: ...
