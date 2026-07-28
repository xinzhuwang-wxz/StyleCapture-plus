from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from stylecapture_backend.features.account.domain import (
    Account,
    AccountBindingConflictError,
    AuthorizationCodeReplayError,
    DeletionRequest,
    DeviceSession,
    ExternalIdentity,
    RefreshTokenReuseError,
    SessionState,
    SubjectDeletedError,
)
from stylecapture_backend.features.account.infrastructure.models import (
    AccountRecord,
    AppleAuthorizationCodeRecord,
    DeletionRequestRecord,
    DeviceSessionRecord,
    ExternalIdentityRecord,
    SubjectAliasRecord,
    SubjectTombstoneRecord,
    UsedRefreshTokenRecord,
)
from stylecapture_backend.features.account.ports import AccountRepository

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

    async def deletion_request_for(self, subject_id: UUID) -> DeletionRequest | None:
        return self.deletions.get(await self.resolve_subject(subject_id))

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


class SqlAlchemyAccountRepository(AccountRepository):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

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

    async def deletion_request_for(self, subject_id: UUID) -> DeletionRequest | None:
        async with self._sessions() as db:
            canonical = await self._resolve_subject(db, subject_id)
            record = await db.get(DeletionRequestRecord, canonical)
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

    async def _revoke_family_locked(self, session: AsyncSession, family_id: UUID) -> None:
        now = datetime.now(UTC)
        await session.execute(
            update(DeviceSessionRecord)
            .where(DeviceSessionRecord.family_id == family_id)
            .values(state=SessionState.REVOKED.value, revoked_at=now, updated_at=now)
        )


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
