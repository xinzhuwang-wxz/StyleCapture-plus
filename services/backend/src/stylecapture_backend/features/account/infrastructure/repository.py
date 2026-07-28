from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from stylecapture_backend.features.account.domain import (
    Account,
    AccountBindingConflictError,
    AccountDeletionAcceptance,
    AppleProviderGrant,
    AppleProviderGrantRevocationAttempt,
    AppleProviderGrantRevocationClaim,
    AuthorizationCodeReplayError,
    DeletionRequest,
    DeviceSession,
    ExternalIdentity,
    RefreshTokenReuseError,
    SessionState,
    SubjectDeletedError,
)
from stylecapture_backend.features.account.infrastructure.models import (
    AccountDeletionIdempotencyRecord,
    AccountRecord,
    AppleAuthorizationCodeRecord,
    AppleProviderGrantRecord,
    DeletionRequestRecord,
    DeviceSessionRecord,
    ExternalIdentityRecord,
    SubjectAliasRecord,
    SubjectTombstoneRecord,
    UsedRefreshTokenRecord,
)
from stylecapture_backend.features.account.ports import (
    AccountRepository,
    AppleProviderGrantRepository,
)

OWNER_TABLES = (
    "captures",
    "items",
    "looks",
    "preference_signals",
    "outfit_purchase_demands",
    "outfit_workflow_traces",
    "render_artifacts",
    "pixel_trials",
    "item_presentation_assets",
)


class AppleProviderGrantCipher:
    def __init__(self, encryption_key: str) -> None:
        self._cipher = Fernet(encryption_key.encode("utf-8"))

    def encrypt_token(self, token: str | None) -> str | None:
        if token is None:
            return None
        return self._cipher.encrypt(token.encode("utf-8")).decode("ascii")

    def decrypt_token(self, encrypted_token: str | None) -> str | None:
        if encrypted_token is None:
            return None
        return self._cipher.decrypt(encrypted_token.encode("ascii")).decode("utf-8")


class InMemoryAccountRepository(AccountRepository):
    def __init__(self) -> None:
        self.accounts: dict[UUID, Account] = {}
        self.identities: dict[tuple[str, str], ExternalIdentity] = {}
        self.aliases: dict[UUID, UUID] = {}
        self.sessions: dict[UUID, DeviceSession] = {}
        self.refresh_index: dict[str, UUID] = {}
        self.used_refresh_hashes: dict[str, UUID] = {}
        self.access_index: dict[str, UUID] = {}
        self.authorization_code_hashes: set[str] = set()
        self.tombstones: set[UUID] = set()
        self.deletions: dict[UUID, DeletionRequest] = {}
        self.apple_provider_grants: dict[UUID, AppleProviderGrant] = {}
        self.apple_provider_grant_ids: dict[UUID, UUID] = {}
        self.apple_provider_grant_generations: dict[UUID, int] = {}
        self.apple_provider_revocation_status: dict[UUID, str] = {}
        self.apple_provider_revocation_failure_code: dict[UUID, str] = {}
        self.apple_provider_revocation_lease_owner: dict[UUID, str] = {}
        self.deletion_idempotency: dict[tuple[str, str], UUID] = {}
        self.deletion_idempotency_by_key: dict[str, tuple[str, UUID]] = {}
        self._owned_records: dict[UUID, list[str]] = defaultdict(list)
        self._subject_write_locks: defaultdict[UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

    @asynccontextmanager
    async def subject_write(self, subject_id: UUID) -> AsyncIterator[UUID]:
        async with self._subject_write_lock(subject_id, require_active=True) as canonical:
            yield canonical

    async def resolve_subject(self, subject_id: UUID) -> UUID:
        seen: set[UUID] = set()
        current = subject_id
        while current in self.aliases and current not in seen:
            seen.add(current)
            current = self.aliases[current]
        return current

    async def assert_can_write(self, subject_id: UUID) -> None:
        canonical = await self.resolve_subject(subject_id)
        if canonical in self.tombstones:
            raise SubjectDeletedError("subject deleted")

    async def bind_apple_identity(
        self,
        *,
        anonymous_subject: UUID,
        identity: ExternalIdentity,
        authorization_code_hash: str,
        account: Account,
        apple_provider_grant: AppleProviderGrant | None = None,
    ) -> Account:
        if authorization_code_hash in self.authorization_code_hashes:
            raise AuthorizationCodeReplayError("authorization code replayed")
        await self.assert_can_write(anonymous_subject)
        existing_identity = self.identities.get((identity.provider, identity.provider_subject))
        canonical = existing_identity.account_subject if existing_identity else account.subject_id
        source = await self.resolve_subject(anonymous_subject)
        source_has_identity = any(
            candidate.account_subject == source for candidate in self.identities.values()
        )
        if source_has_identity and source != canonical:
            raise AccountBindingConflictError("account already bound to another identity")
        if apple_provider_grant is not None:
            self._store_apple_provider_grant(canonical, apple_provider_grant)
        canonical_account = self.accounts.setdefault(canonical, account)
        self.identities.setdefault(
            (identity.provider, identity.provider_subject),
            ExternalIdentity(
                provider=identity.provider,
                provider_subject=identity.provider_subject,
                account_subject=canonical,
                created_at=identity.created_at,
            ),
        )
        if source != canonical:
            self.aliases[anonymous_subject] = canonical
            self.aliases[source] = canonical
            self._owned_records[canonical].extend(self._owned_records.pop(source, []))
        self.authorization_code_hashes.add(authorization_code_hash)
        return canonical_account

    def _store_apple_provider_grant(self, canonical: UUID, grant: AppleProviderGrant) -> None:
        if not grant.access_token or not grant.refresh_token:
            raise RuntimeError("Apple provider grant storage requires access and refresh tokens")
        self.apple_provider_grants[canonical] = grant
        self.apple_provider_grant_ids.setdefault(canonical, uuid4())
        self.apple_provider_grant_generations[canonical] = (
            self.apple_provider_grant_generations.get(canonical, 0) + 1
        )
        self.apple_provider_revocation_status[canonical] = "active"
        self.apple_provider_revocation_failure_code.pop(canonical, None)
        self.apple_provider_revocation_lease_owner.pop(canonical, None)

    async def save_session(self, session: DeviceSession) -> None:
        await self.assert_can_write(UUID(session.account_subject))
        self.sessions[session.id] = session
        self.refresh_index[session.refresh_token_hash] = session.id
        if session.access_token_hash is not None:
            self.access_index[session.access_token_hash] = session.id

    async def rotate_session(
        self,
        *,
        session_id: UUID,
        old_refresh_token_hash: str,
        rotated: DeviceSession,
    ) -> None:
        if self.refresh_index.get(old_refresh_token_hash) != session_id:
            family_id = self.used_refresh_hashes.get(old_refresh_token_hash)
            if family_id is not None:
                await self.revoke_session_family(family_id)
            raise RefreshTokenReuseError("refresh token reuse")
        session = self.sessions[session_id]
        self.refresh_index.pop(old_refresh_token_hash, None)
        self.used_refresh_hashes[old_refresh_token_hash] = session.family_id
        if session.access_token_hash is not None:
            self.access_index.pop(session.access_token_hash, None)
        self.sessions[session_id] = rotated
        self.refresh_index[rotated.refresh_token_hash] = session_id
        if rotated.access_token_hash is not None:
            self.access_index[rotated.access_token_hash] = session_id

    async def find_by_refresh_hash(self, refresh_token_hash: str) -> DeviceSession | None:
        session_id = self.refresh_index.get(refresh_token_hash)
        if session_id is not None:
            return self.sessions[session_id]
        family_id = self.used_refresh_hashes.get(refresh_token_hash)
        if family_id is not None:
            await self.revoke_session_family(family_id)
        return None

    async def find_by_access_hash(self, access_token_hash: str) -> DeviceSession | None:
        session_id = self.access_index.get(access_token_hash)
        return self.sessions.get(session_id) if session_id is not None else None

    async def revoke_session_family(self, family_id: UUID) -> None:
        now = datetime.now(UTC)
        for session_id, session in list(self.sessions.items()):
            if session.family_id == family_id and session.state is SessionState.ACTIVE:
                revoked = session.revoke(now)
                self.sessions[session_id] = revoked
                self.refresh_index.pop(revoked.refresh_token_hash, None)

    async def revoke_subject_sessions(self, subject_id: UUID) -> None:
        now = datetime.now(UTC)
        canonical = await self.resolve_subject(subject_id)
        for session_id, session in list(self.sessions.items()):
            if UUID(session.account_subject) == canonical and session.state is SessionState.ACTIVE:
                revoked = session.revoke(now)
                self.sessions[session_id] = revoked
                self.refresh_index.pop(revoked.refresh_token_hash, None)

    async def tombstone_subject(self, subject_id: UUID, *, reason: str) -> DeletionRequest:
        async with self._subject_write_lock(subject_id, require_active=False) as canonical:
            now = datetime.now(UTC)
            self.tombstones.add(canonical)
            deletion = self.deletions.get(canonical) or DeletionRequest(
                subject_id=canonical,
                status="frozen",
                requested_at=now,
                updated_at=now,
            )
            self.deletions[canonical] = deletion
            return deletion

    async def accept_account_deletion(
        self,
        subject_id: UUID,
        *,
        reason: str,
        access_token_hash: str | None = None,
        idempotency_key_hash: str | None = None,
    ) -> AccountDeletionAcceptance:
        async with self._subject_write_lock(subject_id, require_active=False) as canonical:
            now = datetime.now(UTC)
            self.tombstones.add(canonical)
            deletion = self.deletions.get(canonical) or DeletionRequest(
                subject_id=canonical,
                status="frozen",
                requested_at=now,
                updated_at=now,
            )
            self.deletions[canonical] = deletion
            for session_id, session in list(self.sessions.items()):
                if UUID(session.account_subject) == canonical and session.state is SessionState.ACTIVE:
                    revoked = session.revoke(now)
                    self.sessions[session_id] = revoked
                    self.refresh_index.pop(revoked.refresh_token_hash, None)
            attempt = None
            grant = self.apple_provider_grants.get(canonical)
            if grant is not None and self.apple_provider_revocation_status.get(canonical) != "revoked":
                self.apple_provider_revocation_status[canonical] = "pending"
                self.apple_provider_revocation_failure_code.pop(canonical, None)
                attempt = AppleProviderGrantRevocationAttempt(
                    grant_id=self.apple_provider_grant_ids[canonical],
                    generation=self.apple_provider_grant_generations[canonical],
                    lease_owner="inline-deletion",
                    grant=grant,
                )
            if access_token_hash is not None and idempotency_key_hash is not None:
                existing_replay = self.deletion_idempotency_by_key.get(idempotency_key_hash)
                if existing_replay is not None and existing_replay != (access_token_hash, canonical):
                    raise AccountBindingConflictError("deletion idempotency key conflict")
                self.deletion_idempotency_by_key[idempotency_key_hash] = (
                    access_token_hash,
                    canonical,
                )
                self.deletion_idempotency[(access_token_hash, idempotency_key_hash)] = canonical
            return AccountDeletionAcceptance(
                deletion=deletion,
                apple_revocation_attempt=attempt,
            )

    async def deletion_request_for_idempotency(
        self,
        *,
        access_token_hash: str,
        idempotency_key_hash: str,
    ) -> DeletionRequest | None:
        subject_id = self.deletion_idempotency.get((access_token_hash, idempotency_key_hash))
        if subject_id is None:
            return None
        return self.deletions.get(subject_id)

    async def remember_owned_record(self, subject_id: UUID, record_id: str) -> None:
        self._owned_records[subject_id].append(record_id)

    async def owned_records_for(self, subject_id: UUID) -> list[str]:
        return list(self._owned_records.get(subject_id, []))

    @asynccontextmanager
    async def _subject_write_lock(
        self,
        subject_id: UUID,
        *,
        require_active: bool,
    ) -> AsyncIterator[UUID]:
        async with self._subject_write_locks[subject_id]:
            canonical = await self.resolve_subject(subject_id)
            if canonical == subject_id:
                if require_active:
                    await self.assert_can_write(canonical)
                yield canonical
                return
            async with self._subject_write_locks[canonical]:
                if require_active:
                    await self.assert_can_write(canonical)
                yield canonical


class InMemoryAppleProviderGrantRepository(AppleProviderGrantRepository):
    def __init__(self, subjects: InMemoryAccountRepository) -> None:
        self._subjects = subjects
        self.grants = subjects.apple_provider_grants
        self.grant_ids = subjects.apple_provider_grant_ids
        self.grant_generations = subjects.apple_provider_grant_generations
        self.revocation_status = subjects.apple_provider_revocation_status
        self.revocation_failure_code = subjects.apple_provider_revocation_failure_code
        self.revocation_lease_owner = subjects.apple_provider_revocation_lease_owner

    async def claim_apple_provider_revocations(
        self,
        *,
        lease_owner: str,
        limit: int,
    ) -> list[AppleProviderGrantRevocationClaim]:
        claims: list[AppleProviderGrantRevocationClaim] = []
        for canonical, grant in self.grants.items():
            if len(claims) >= limit:
                break
            if self.revocation_status.get(canonical) not in {"pending", "failed"}:
                continue
            self.revocation_status[canonical] = "attempted"
            self.revocation_failure_code.pop(canonical, None)
            self.revocation_lease_owner[canonical] = lease_owner
            claims.append(
                AppleProviderGrantRevocationClaim(
                    attempt=AppleProviderGrantRevocationAttempt(
                        grant_id=self.grant_ids[canonical],
                        generation=self.grant_generations[canonical],
                        lease_owner=lease_owner,
                        grant=grant,
                    ),
                    lease_owner=lease_owner,
                )
            )
        return claims

    async def mark_apple_provider_revoked(
        self,
        attempt: AppleProviderGrantRevocationAttempt,
    ) -> None:
        canonical = self._canonical_for_attempt(attempt)
        if canonical is None:
            return
        if self.revocation_status.get(canonical) != "attempted":
            return
        if self.revocation_lease_owner.get(canonical) != attempt.lease_owner:
            return
        grant = self.grants.get(canonical)
        if grant is not None:
            self.grants[canonical] = AppleProviderGrant(
                provider_subject=grant.provider_subject,
                access_token=None,
                refresh_token=None,
                issued_at=grant.issued_at,
            )
            self.revocation_status[canonical] = "revoked"
            self.revocation_failure_code.pop(canonical, None)
            self.revocation_lease_owner.pop(canonical, None)

    async def mark_apple_provider_revocation_failed(
        self,
        attempt: AppleProviderGrantRevocationAttempt,
        *,
        failure_code: str,
    ) -> None:
        canonical = self._canonical_for_attempt(attempt)
        if (
            canonical is not None
            and canonical in self.grants
            and self.revocation_status.get(canonical) == "attempted"
            and self.revocation_lease_owner.get(canonical) == attempt.lease_owner
        ):
            self.revocation_status[canonical] = "failed"
            self.revocation_failure_code[canonical] = failure_code
            self.revocation_lease_owner.pop(canonical, None)

    def _canonical_for_attempt(
        self,
        attempt: AppleProviderGrantRevocationAttempt,
    ) -> UUID | None:
        for canonical, grant_id in self.grant_ids.items():
            if grant_id == attempt.grant_id and self.grant_generations.get(canonical) == attempt.generation:
                return canonical
        return None


class SqlAlchemyAccountRepository(AccountRepository):
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        apple_provider_grant_cipher: AppleProviderGrantCipher | None = None,
    ) -> None:
        self._sessions = sessions
        self._apple_provider_grant_cipher = apple_provider_grant_cipher

    @asynccontextmanager
    async def subject_write(self, subject_id: UUID) -> AsyncIterator[UUID]:
        async with self._sessions() as session, session.begin():
            canonical = await self._lock_subject(
                session,
                subject_id,
                require_active=True,
            )
            yield canonical

    async def resolve_subject(self, subject_id: UUID) -> UUID:
        async with self._sessions() as session:
            return await self._resolve_subject(session, subject_id)

    async def assert_can_write(self, subject_id: UUID) -> None:
        async with self._sessions() as session:
            canonical = await self._resolve_subject(session, subject_id)
            tombstone = await session.get(SubjectTombstoneRecord, canonical)
            if tombstone is not None:
                raise SubjectDeletedError("subject deleted")

    async def bind_apple_identity(
        self,
        *,
        anonymous_subject: UUID,
        identity: ExternalIdentity,
        authorization_code_hash: str,
        account: Account,
        apple_provider_grant: AppleProviderGrant | None = None,
    ) -> Account:
        async with self._sessions() as session, session.begin():
            await self._acquire_binding_lock(
                session,
                namespace="anonymous-subject",
                value=str(anonymous_subject),
            )
            await self._acquire_binding_lock(
                session,
                namespace="authorization-code",
                value=authorization_code_hash,
            )
            await self._acquire_binding_lock(
                session,
                namespace="external-identity",
                value=f"{identity.provider}:{identity.provider_subject}",
            )
            existing_code = await session.get(
                AppleAuthorizationCodeRecord,
                authorization_code_hash,
            )
            if existing_code is not None:
                raise AuthorizationCodeReplayError("authorization code replayed")
            source_subject = await self._lock_subject(
                session,
                anonymous_subject,
                require_active=True,
            )
            existing_identity = (
                await session.execute(
                    select(ExternalIdentityRecord).where(
                        ExternalIdentityRecord.provider == identity.provider,
                        ExternalIdentityRecord.provider_subject == identity.provider_subject,
                    )
                )
            ).scalar_one_or_none()
            canonical = (
                existing_identity.account_subject
                if existing_identity is not None
                else account.subject_id
            )
            canonical = await self._lock_subject(
                session,
                canonical,
                require_active=True,
            )
            source_has_identity = (
                await session.execute(
                    select(ExternalIdentityRecord.id)
                    .where(ExternalIdentityRecord.account_subject == source_subject)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if source_has_identity is not None and source_subject != canonical:
                raise AccountBindingConflictError("account already bound to another identity")
            existing_account = await session.get(AccountRecord, canonical)
            if existing_account is None:
                session.add(
                    AccountRecord(
                        subject_id=canonical,
                        created_at=account.created_at,
                    )
                )
            if existing_identity is None:
                session.add(
                    ExternalIdentityRecord(
                        id=uuid4(),
                        provider=identity.provider,
                        provider_subject=identity.provider_subject,
                        account_subject=canonical,
                        created_at=identity.created_at,
                    )
                )
            session.add(
                AppleAuthorizationCodeRecord(
                    code_hash=authorization_code_hash,
                    account_subject=canonical,
                    used_at=identity.created_at,
                )
            )
            if apple_provider_grant is not None:
                await self._upsert_apple_provider_grant_locked(
                    session,
                    account_subject=canonical,
                    grant=apple_provider_grant,
                )
            if source_subject != canonical:
                await session.merge(
                    SubjectAliasRecord(
                        subject_id=anonymous_subject,
                        canonical_subject_id=canonical,
                        created_at=identity.created_at,
                    )
                )
                await session.merge(
                    SubjectAliasRecord(
                        subject_id=source_subject,
                        canonical_subject_id=canonical,
                        created_at=identity.created_at,
                    )
                )
                for table in OWNER_TABLES:
                    await session.execute(
                        text(f"UPDATE {table} SET user_id = :canonical WHERE user_id = :source"),
                        {"canonical": canonical, "source": source_subject},
                    )
        return Account(subject_id=canonical, created_at=account.created_at)

    async def save_session(self, session: DeviceSession) -> None:
        async with self._sessions() as db, db.begin():
            await self._lock_subject(
                db,
                UUID(session.account_subject),
                require_active=True,
            )
            db.add(_session_record(session))

    async def rotate_session(
        self,
        *,
        session_id: UUID,
        old_refresh_token_hash: str,
        rotated: DeviceSession,
    ) -> None:
        async with self._sessions() as db, db.begin():
            record = await db.get(DeviceSessionRecord, session_id, with_for_update=True)
            if record is None or record.refresh_token_hash != old_refresh_token_hash:
                family_id = await db.get(UsedRefreshTokenRecord, old_refresh_token_hash)
                if family_id is not None:
                    await self._revoke_family_locked(db, family_id.family_id)
                raise RefreshTokenReuseError("refresh token reuse")
            await self._lock_subject(
                db,
                record.account_subject,
                require_active=True,
            )
            db.add(
                UsedRefreshTokenRecord(
                    refresh_token_hash=old_refresh_token_hash,
                    family_id=record.family_id,
                    used_at=rotated.updated_at,
                )
            )
            _apply_session(record, rotated)

    async def find_by_refresh_hash(self, refresh_token_hash: str) -> DeviceSession | None:
        async with self._sessions() as db:
            record = (
                await db.execute(
                    select(DeviceSessionRecord).where(
                        DeviceSessionRecord.refresh_token_hash == refresh_token_hash
                    )
                )
            ).scalar_one_or_none()
            if record is not None:
                return _session_from_record(record)
            used = await db.get(UsedRefreshTokenRecord, refresh_token_hash)
            if used is not None:
                await self._revoke_family_locked(db, used.family_id)
                await db.commit()
            return None

    async def find_by_access_hash(self, access_token_hash: str) -> DeviceSession | None:
        async with self._sessions() as db:
            record = (
                await db.execute(
                    select(DeviceSessionRecord).where(
                        DeviceSessionRecord.access_token_hash == access_token_hash
                    )
                )
            ).scalar_one_or_none()
            return _session_from_record(record) if record is not None else None

    async def revoke_session_family(self, family_id: UUID) -> None:
        async with self._sessions() as db, db.begin():
            await self._revoke_family_locked(db, family_id)

    async def revoke_subject_sessions(self, subject_id: UUID) -> None:
        async with self._sessions() as db, db.begin():
            canonical = await self._resolve_subject(db, subject_id)
            now = datetime.now(UTC)
            await db.execute(
                update(DeviceSessionRecord)
                .where(DeviceSessionRecord.account_subject == canonical)
                .values(state=SessionState.REVOKED.value, revoked_at=now, updated_at=now)
            )

    async def tombstone_subject(self, subject_id: UUID, *, reason: str) -> DeletionRequest:
        async with self._sessions() as db:
            async with db.begin():
                canonical = await self._lock_subject(
                    db,
                    subject_id,
                    require_active=False,
                )
                now = datetime.now(UTC)
                await db.merge(
                    SubjectTombstoneRecord(
                        subject_id=canonical,
                        reason=reason,
                        created_at=now,
                    )
                )
                deletion = await db.get(DeletionRequestRecord, canonical)
                if deletion is None:
                    deletion = DeletionRequestRecord(
                        subject_id=canonical,
                        status="frozen",
                        requested_at=now,
                        updated_at=now,
                    )
                    db.add(deletion)
            return DeletionRequest(
                subject_id=canonical,
                status="frozen",
                requested_at=deletion.requested_at,
                updated_at=deletion.updated_at,
            )

    async def accept_account_deletion(
        self,
        subject_id: UUID,
        *,
        reason: str,
        access_token_hash: str | None = None,
        idempotency_key_hash: str | None = None,
    ) -> AccountDeletionAcceptance:
        async with self._sessions() as db:
            async with db.begin():
                canonical = await self._lock_subject(
                    db,
                    subject_id,
                    require_active=False,
                )
                now = datetime.now(UTC)
                await db.merge(
                    SubjectTombstoneRecord(
                        subject_id=canonical,
                        reason=reason,
                        created_at=now,
                    )
                )
                deletion = await db.get(DeletionRequestRecord, canonical)
                if deletion is None:
                    deletion = DeletionRequestRecord(
                        subject_id=canonical,
                        status="frozen",
                        requested_at=now,
                        updated_at=now,
                    )
                    db.add(deletion)
                else:
                    deletion.status = "frozen"
                    deletion.updated_at = now
                await db.execute(
                    update(DeviceSessionRecord)
                    .where(DeviceSessionRecord.account_subject == canonical)
                    .values(state=SessionState.REVOKED.value, revoked_at=now, updated_at=now)
                )
                if access_token_hash is not None and idempotency_key_hash is not None:
                    replay = await db.get(
                        AccountDeletionIdempotencyRecord,
                        idempotency_key_hash,
                        with_for_update=True,
                    )
                    if replay is None:
                        db.add(
                            AccountDeletionIdempotencyRecord(
                                idempotency_key_hash=idempotency_key_hash,
                                access_token_hash=access_token_hash,
                                account_subject=canonical,
                                deletion_subject=canonical,
                                created_at=now,
                            )
                        )
                    elif (
                        replay.access_token_hash != access_token_hash
                        or replay.account_subject != canonical
                    ):
                        raise AccountBindingConflictError("deletion idempotency key conflict")
                    else:
                        replay.deletion_subject = canonical
                attempt = await self._capture_apple_revocation_attempt_locked(
                    db,
                    account_subject=canonical,
                    now=now,
                )
            return AccountDeletionAcceptance(
                deletion=DeletionRequest(
                    subject_id=canonical,
                    status="frozen",
                    requested_at=deletion.requested_at,
                    updated_at=deletion.updated_at,
                ),
                apple_revocation_attempt=attempt,
            )

    async def deletion_request_for_idempotency(
        self,
        *,
        access_token_hash: str,
        idempotency_key_hash: str,
    ) -> DeletionRequest | None:
        async with self._sessions() as db:
            replay = await db.get(AccountDeletionIdempotencyRecord, idempotency_key_hash)
            if replay is None or replay.access_token_hash != access_token_hash:
                return None
            record = await db.get(DeletionRequestRecord, replay.deletion_subject)
            if record is None:
                return None
            return DeletionRequest(
                subject_id=record.subject_id,
                status=record.status,
                requested_at=record.requested_at,
                updated_at=record.updated_at,
            )

    async def _resolve_subject(self, session: AsyncSession, subject_id: UUID) -> UUID:
        seen: set[UUID] = set()
        current = subject_id
        while current not in seen:
            seen.add(current)
            alias = await session.get(SubjectAliasRecord, current)
            if alias is None:
                return current
            current = alias.canonical_subject_id
        return current

    async def _assert_can_write_locked(self, session: AsyncSession, subject_id: UUID) -> None:
        canonical = await self._resolve_subject(session, subject_id)
        if await session.get(SubjectTombstoneRecord, canonical) is not None:
            raise SubjectDeletedError("subject deleted")

    async def _lock_subject(
        self,
        session: AsyncSession,
        subject_id: UUID,
        *,
        require_active: bool,
    ) -> UUID:
        await self._acquire_binding_lock(
            session,
            namespace="subject-write",
            value=str(subject_id),
        )
        canonical = await self._resolve_subject(session, subject_id)
        if canonical != subject_id:
            await self._acquire_binding_lock(
                session,
                namespace="subject-write",
                value=str(canonical),
            )
        if require_active:
            await self._assert_can_write_locked(session, canonical)
        return canonical

    async def _acquire_binding_lock(
        self,
        session: AsyncSession,
        *,
        namespace: str,
        value: str,
    ) -> None:
        lock_key = sha256(f"{namespace}:{value}".encode()).hexdigest()
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": lock_key},
        )

    async def _upsert_apple_provider_grant_locked(
        self,
        session: AsyncSession,
        *,
        account_subject: UUID,
        grant: AppleProviderGrant,
    ) -> None:
        if self._apple_provider_grant_cipher is None:
            raise RuntimeError("Apple provider grant encryption is not configured")
        if not grant.access_token or not grant.refresh_token:
            raise RuntimeError("Apple provider grant storage requires access and refresh tokens")
        now = grant.issued_at.astimezone(UTC)
        latest = (
            await session.execute(
                select(AppleProviderGrantRecord)
                .where(
                    AppleProviderGrantRecord.provider == "apple",
                    AppleProviderGrantRecord.account_subject == account_subject,
                )
                .order_by(AppleProviderGrantRecord.generation.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if latest is not None and latest.revocation_status == "active":
            latest.revocation_status = "pending"
            latest.revocation_failure_code = None
            latest.revocation_lease_owner = None
            latest.revocation_lease_expires_at = None
            latest.updated_at = now
        encrypted_access = self._apple_provider_grant_cipher.encrypt_token(grant.access_token)
        encrypted_refresh = self._apple_provider_grant_cipher.encrypt_token(grant.refresh_token)
        session.add(
            AppleProviderGrantRecord(
                id=uuid4(),
                provider="apple",
                provider_subject=grant.provider_subject,
                account_subject=account_subject,
                generation=1 if latest is None else latest.generation + 1,
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                created_at=now,
                updated_at=now,
                revocation_status="active",
                revocation_attempt_count=0,
            )
        )

    async def _capture_apple_revocation_attempt_locked(
        self,
        session: AsyncSession,
        *,
        account_subject: UUID,
        now: datetime,
    ) -> AppleProviderGrantRevocationAttempt | None:
        await session.execute(
            update(AppleProviderGrantRecord)
            .where(
                AppleProviderGrantRecord.provider == "apple",
                AppleProviderGrantRecord.account_subject == account_subject,
                AppleProviderGrantRecord.revocation_status.in_(("active", "pending", "failed")),
            )
            .values(
                revocation_status="pending",
                revocation_failure_code=None,
                revocation_lease_owner=None,
                revocation_lease_expires_at=None,
                updated_at=now,
            )
        )
        return None

    async def _revoke_family_locked(self, session: AsyncSession, family_id: UUID) -> None:
        now = datetime.now(UTC)
        await session.execute(
            update(DeviceSessionRecord)
            .where(DeviceSessionRecord.family_id == family_id)
            .values(state=SessionState.REVOKED.value, revoked_at=now, updated_at=now)
        )


class SqlAlchemyAppleProviderGrantRepository(AppleProviderGrantRepository):
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        cipher: AppleProviderGrantCipher,
    ) -> None:
        self._sessions = sessions
        self._cipher = cipher

    async def claim_apple_provider_revocations(
        self,
        *,
        lease_owner: str,
        limit: int,
    ) -> list[AppleProviderGrantRevocationClaim]:
        now = datetime.now(UTC)
        lease_expires_at = now + timedelta(minutes=5)
        async with self._sessions() as session, session.begin():
            statement = (
                select(AppleProviderGrantRecord)
                .where(
                    AppleProviderGrantRecord.revocation_status.in_(("pending", "failed")),
                    (
                        AppleProviderGrantRecord.revocation_lease_expires_at.is_(None)
                        | (AppleProviderGrantRecord.revocation_lease_expires_at <= now)
                    ),
                )
                .order_by(AppleProviderGrantRecord.updated_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            grants = list((await session.execute(statement)).scalars())
            claims: list[AppleProviderGrantRevocationClaim] = []
            for grant in grants:
                grant.revocation_status = "attempted"
                grant.revocation_attempted_at = now
                grant.revocation_failure_code = None
                grant.revocation_attempt_count += 1
                grant.revocation_lease_owner = lease_owner
                grant.revocation_lease_expires_at = lease_expires_at
                grant.updated_at = now
                try:
                    access_token = self._cipher.decrypt_token(grant.encrypted_access_token)
                    refresh_token = self._cipher.decrypt_token(grant.encrypted_refresh_token)
                except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError):
                    grant.revocation_status = "failed"
                    grant.revocation_failure_code = "apple_grant_unreadable"
                    grant.revocation_lease_owner = None
                    grant.revocation_lease_expires_at = None
                    continue
                claims.append(
                    AppleProviderGrantRevocationClaim(
                        attempt=AppleProviderGrantRevocationAttempt(
                            grant_id=grant.id,
                            generation=grant.generation,
                            lease_owner=lease_owner,
                            grant=AppleProviderGrant(
                                provider_subject=grant.provider_subject,
                                access_token=access_token,
                                refresh_token=refresh_token,
                                issued_at=grant.created_at,
                            ),
                        ),
                        lease_owner=lease_owner,
                    )
                )
            return claims

    async def mark_apple_provider_revocation_attempted(self, subject_id: UUID) -> None:
        async with self._sessions() as session, session.begin():
            grant = await self._find_grant(session, subject_id, lock=True)
            if grant is None:
                return
            now = datetime.now(UTC)
            grant.revocation_status = "attempted"
            grant.revocation_attempted_at = now
            grant.revocation_failure_code = None
            grant.updated_at = now

    async def mark_apple_provider_revoked(
        self,
        attempt: AppleProviderGrantRevocationAttempt,
    ) -> None:
        await self._mark_revocation_status(
            attempt,
            status="revoked",
            failure_code=None,
            revoked=True,
        )

    async def mark_apple_provider_revocation_failed(
        self,
        attempt: AppleProviderGrantRevocationAttempt,
        *,
        failure_code: str,
    ) -> None:
        await self._mark_revocation_status(
            attempt,
            status="failed",
            failure_code=failure_code,
            revoked=False,
        )

    async def _mark_revocation_status(
        self,
        attempt: AppleProviderGrantRevocationAttempt,
        *,
        status: str,
        failure_code: str | None,
        revoked: bool,
    ) -> None:
        async with self._sessions() as session, session.begin():
            grant = await session.get(
                AppleProviderGrantRecord,
                attempt.grant_id,
                with_for_update=True,
            )
            if grant is None:
                return
            if grant.generation != attempt.generation:
                return
            if grant.revocation_status != "attempted":
                return
            if grant.revocation_lease_owner != attempt.lease_owner:
                return
            now = datetime.now(UTC)
            grant.revocation_status = status
            grant.revocation_attempted_at = now
            grant.revocation_failure_code = failure_code
            grant.revocation_lease_owner = None
            grant.revocation_lease_expires_at = None
            grant.updated_at = now
            if revoked:
                grant.revoked_at = now
                grant.encrypted_access_token = None
                grant.encrypted_refresh_token = None

    async def _find_grant(
        self,
        session: AsyncSession,
        subject_id: UUID,
        *,
        lock: bool,
    ) -> AppleProviderGrantRecord | None:
        canonical = await self._resolve_subject(session, subject_id)
        statement = select(AppleProviderGrantRecord).where(
            AppleProviderGrantRecord.provider == "apple",
            AppleProviderGrantRecord.account_subject == canonical,
        ).order_by(AppleProviderGrantRecord.generation.desc()).limit(1)
        if lock:
            statement = statement.with_for_update()
        return (await session.execute(statement)).scalar_one_or_none()

    async def _resolve_subject(self, session: AsyncSession, subject_id: UUID) -> UUID:
        seen: set[UUID] = set()
        current = subject_id
        while current not in seen:
            seen.add(current)
            alias = await session.get(SubjectAliasRecord, current)
            if alias is None:
                return current
            current = alias.canonical_subject_id
        return current

def _session_record(session: DeviceSession) -> DeviceSessionRecord:
    return DeviceSessionRecord(
        id=session.id,
        family_id=session.family_id,
        account_subject=UUID(session.account_subject),
        refresh_token_hash=session.refresh_token_hash,
        access_token_hash=session.access_token_hash,
        access_expires_at=session.access_expires_at,
        refresh_expires_at=session.refresh_expires_at,
        state=session.state.value,
        device_name=session.device_name,
        created_at=session.created_at,
        updated_at=session.updated_at,
        revoked_at=session.revoked_at,
    )


def _apply_session(record: DeviceSessionRecord, session: DeviceSession) -> None:
    record.refresh_token_hash = session.refresh_token_hash
    record.access_token_hash = session.access_token_hash
    record.access_expires_at = session.access_expires_at
    record.refresh_expires_at = session.refresh_expires_at
    record.state = session.state.value
    record.updated_at = session.updated_at
    record.revoked_at = session.revoked_at


def _session_from_record(record: DeviceSessionRecord) -> DeviceSession:
    return DeviceSession(
        id=record.id,
        family_id=record.family_id,
        account_subject=str(record.account_subject),
        refresh_token_hash=record.refresh_token_hash,
        access_token_hash=record.access_token_hash,
        access_expires_at=record.access_expires_at,
        refresh_expires_at=record.refresh_expires_at,
        state=SessionState(record.state),
        device_name=record.device_name,
        created_at=record.created_at,
        updated_at=record.updated_at,
        revoked_at=record.revoked_at,
    )
