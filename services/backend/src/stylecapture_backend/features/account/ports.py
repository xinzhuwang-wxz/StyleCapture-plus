from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.account.domain import (
    Account,
    AppleIdentityClaims,
    DeletionRequest,
    DeviceSession,
    ExternalIdentity,
)


class AppleIdentityVerifier(Protocol):
    async def verify(
        self,
        identity_token: str,
        authorization_code: str,
    ) -> AppleIdentityClaims: ...


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

    async def deletion_request_for(self, subject_id: UUID) -> DeletionRequest | None: ...
