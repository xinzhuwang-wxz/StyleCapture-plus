from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import jwt
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import String, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from stylecapture_backend.features.account.application import (
    AccountApplication,
    AuthenticateWithAppleCommand,
)
from stylecapture_backend.features.account.domain import (
    Account,
    AccountDeletionAcceptance,
    AppleIdentityClaims,
    AppleProviderGrant,
    AppleProviderGrantRevocationAttempt,
    DeletionRequest,
    ExternalIdentity,
    ProviderGrantRevocationError,
    SubjectDeletedError,
    hash_nonce,
)
from stylecapture_backend.features.account.infrastructure.apple_identity import (
    AppleAuthorizationGrant,
    AppleJWK,
    PyJWTAppleIdentityVerifier,
)
from stylecapture_backend.features.account.infrastructure.models import (
    AppleProviderGrantRecord,
)
from stylecapture_backend.features.account.infrastructure.repository import (
    AppleProviderGrantCipher,
    SqlAlchemyAccountRepository,
    SqlAlchemyAppleProviderGrantRepository,
)
from stylecapture_backend.platform.database import build_session_factory, run_migrations

TEST_DATABASE_URL = os.environ.get(
    "STYLECAPTURE_TEST_DATABASE_URL",
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture_test",
)
ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")
ISSUED_AT = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)


async def _reset_database() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE account_deletion_idempotency, apple_provider_grants, "
                "apple_authorization_codes, "
                "used_refresh_tokens, device_sessions, subject_aliases, "
                "external_identities, accounts, subject_tombstones, deletion_requests CASCADE"
            )
        )
        await session.commit()


async def _bind_account_with_grant(
    *,
    subject_id: UUID,
    provider_subject: str = "apple-sub-db-grant",
    grant: AppleProviderGrant | None = None,
    repository: SqlAlchemyAccountRepository | None = None,
) -> None:
    repository = repository or _account_repository()
    await repository.bind_apple_identity(
        anonymous_subject=uuid4(),
        identity=ExternalIdentity(
            provider="apple",
            provider_subject=provider_subject,
            account_subject=subject_id,
            created_at=ISSUED_AT,
        ),
        authorization_code_hash=uuid4().hex + uuid4().hex,
        account=Account(subject_id=subject_id, created_at=ISSUED_AT),
        apple_provider_grant=grant or _grant(provider_subject=provider_subject),
    )


def _grant(
    *,
    provider_subject: str = "apple-sub-db-grant",
    access_token: str | None = "apple-access-token-secret",
    refresh_token: str | None = "apple-refresh-token-secret",
) -> AppleProviderGrant:
    return AppleProviderGrant(
        provider_subject=provider_subject,
        access_token=access_token,
        refresh_token=refresh_token,
        issued_at=ISSUED_AT,
    )


def _provider_repository() -> SqlAlchemyAppleProviderGrantRepository:
    return SqlAlchemyAppleProviderGrantRepository(
        build_session_factory(TEST_DATABASE_URL),
        cipher=AppleProviderGrantCipher(ENCRYPTION_KEY),
    )


def _account_repository() -> SqlAlchemyAccountRepository:
    return SqlAlchemyAccountRepository(
        build_session_factory(TEST_DATABASE_URL),
        apple_provider_grant_cipher=AppleProviderGrantCipher(ENCRYPTION_KEY),
    )


@pytest.mark.asyncio
async def test_save_stores_ciphertext_without_plaintext_tokens() -> None:
    await _reset_database()
    subject_id = uuid4()
    await _bind_account_with_grant(subject_id=subject_id)

    async with build_session_factory(TEST_DATABASE_URL)() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT encrypted_access_token, encrypted_refresh_token
                    FROM apple_provider_grants
                    WHERE account_subject = :subject_id
                    """
                ),
                {"subject_id": subject_id},
            )
        ).one()
    assert row.encrypted_access_token != "apple-access-token-secret"
    assert row.encrypted_refresh_token != "apple-refresh-token-secret"


@pytest.mark.asyncio
async def test_claim_decrypts_saved_tokens_for_revocation() -> None:
    await _reset_database()
    subject_id = uuid4()
    repository = _provider_repository()
    await _bind_account_with_grant(
        subject_id=subject_id,
        provider_subject="apple-sub-roundtrip",
        grant=_grant(provider_subject="apple-sub-roundtrip"),
    )
    await _account_repository().accept_account_deletion(subject_id, reason="account_deletion")

    claims = await repository.claim_apple_provider_revocations(
        lease_owner="test-worker",
        limit=10,
    )
    assert [claim.attempt.grant for claim in claims] == [
        _grant(provider_subject="apple-sub-roundtrip")
    ]


@pytest.mark.asyncio
async def test_active_grant_is_not_claimed_by_revocation_sweep() -> None:
    await _reset_database()
    subject_id = uuid4()
    repository = _provider_repository()
    await _bind_account_with_grant(subject_id=subject_id)

    claims = await repository.claim_apple_provider_revocations(
        lease_owner="test-worker",
        limit=10,
    )

    assert claims == []
    async with build_session_factory(TEST_DATABASE_URL)() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT revocation_status, encrypted_refresh_token
                    FROM apple_provider_grants
                    WHERE account_subject = :subject_id
                    """
                ),
                {"subject_id": subject_id},
            )
        ).one()
    assert row.revocation_status == "active"
    assert row.encrypted_refresh_token is not None


@pytest.mark.asyncio
async def test_mark_revoked_wipes_stored_ciphertext() -> None:
    await _reset_database()
    subject_id = uuid4()
    repository = _provider_repository()
    await _bind_account_with_grant(subject_id=subject_id)
    acceptance = await _account_repository().accept_account_deletion(
        subject_id,
        reason="account_deletion",
    )
    claims = await repository.claim_apple_provider_revocations(
        lease_owner="test-worker",
        limit=10,
    )
    assert acceptance.deletion.status == "frozen"
    assert len(claims) == 1

    await repository.mark_apple_provider_revoked(claims[0].attempt)

    async with build_session_factory(TEST_DATABASE_URL)() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT revocation_status, encrypted_access_token, encrypted_refresh_token
                    FROM apple_provider_grants
                    WHERE account_subject = :subject_id
                    """
                ),
                {"subject_id": subject_id},
            )
        ).one()
    assert row.revocation_status == "revoked"
    assert row.encrypted_access_token is None
    assert row.encrypted_refresh_token is None


@pytest.mark.asyncio
async def test_stale_lease_worker_cannot_overwrite_new_revocation_claim() -> None:
    await _reset_database()
    subject_id = uuid4()
    repository = _provider_repository()
    account_repository = _account_repository()
    await _bind_account_with_grant(subject_id=subject_id, repository=account_repository)
    await account_repository.accept_account_deletion(subject_id, reason="account_deletion")

    first_claim = (
        await repository.claim_apple_provider_revocations(
            lease_owner="first-worker",
            limit=10,
        )
    )[0]
    async with build_session_factory(TEST_DATABASE_URL)() as session:
        await session.execute(
            text(
                """
                UPDATE apple_provider_grants
                SET revocation_status = 'failed',
                    revocation_failure_code = 'apple_revocation_failed',
                    revocation_lease_owner = NULL,
                    revocation_lease_expires_at = NULL
                WHERE id = :grant_id
                """
            ),
            {"grant_id": first_claim.attempt.grant_id},
        )
        await session.commit()
    second_claim = (
        await repository.claim_apple_provider_revocations(
            lease_owner="second-worker",
            limit=10,
        )
    )[0]

    await repository.mark_apple_provider_revoked(first_claim.attempt)

    async with build_session_factory(TEST_DATABASE_URL)() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT revocation_status, encrypted_refresh_token, revocation_lease_owner
                    FROM apple_provider_grants
                    WHERE id = :grant_id
                    """
                ),
                {"grant_id": second_claim.attempt.grant_id},
            )
        ).one()
    assert row.revocation_status == "attempted"
    assert row.encrypted_refresh_token is not None
    assert row.revocation_lease_owner == "second-worker"


@pytest.mark.asyncio
async def test_stale_grant_revocation_attempt_cannot_wipe_replacement_generation() -> None:
    await _reset_database()
    subject_id = uuid4()
    provider_subject = "apple-sub-stale-cas"
    repository = _provider_repository()
    await _bind_account_with_grant(
        subject_id=subject_id,
        provider_subject=provider_subject,
        grant=_grant(
            provider_subject=provider_subject,
            refresh_token="old-refresh-token",
        ),
    )
    async with build_session_factory(TEST_DATABASE_URL)() as session:
        stale_row = (
            await session.execute(
                text(
                    """
                    SELECT id, generation
                    FROM apple_provider_grants
                    WHERE account_subject = :subject_id
                    """
                ),
                {"subject_id": subject_id},
            )
        ).one()
    stale_attempt = AppleProviderGrantRevocationAttempt(
        grant_id=stale_row.id,
        generation=stale_row.generation,
        lease_owner="stale-worker",
        grant=_grant(
            provider_subject=provider_subject,
            refresh_token="old-refresh-token",
        ),
    )
    await _bind_account_with_grant(
        subject_id=subject_id,
        provider_subject=provider_subject,
        grant=_grant(
            provider_subject=provider_subject,
            refresh_token="new-refresh-token",
        ),
    )

    await repository.mark_apple_provider_revoked(stale_attempt)

    async with build_session_factory(TEST_DATABASE_URL)() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT generation, revocation_status, encrypted_refresh_token
                    FROM apple_provider_grants
                    WHERE account_subject = :subject_id
                    """
                ),
                {"subject_id": subject_id},
            )
        ).all()
    assert len(rows) == 2
    replacement = max(rows, key=lambda row: row.generation)
    assert replacement.generation == stale_row.generation + 1
    assert replacement.revocation_status == "active"
    assert replacement.encrypted_refresh_token is not None


@pytest.mark.asyncio
async def test_replacement_without_refresh_token_keeps_existing_grant_active() -> None:
    await _reset_database()
    subject_id = uuid4()
    provider_subject = "apple-sub-missing-refresh-replacement"
    account_repository = _account_repository()
    provider_repository = _provider_repository()
    await _bind_account_with_grant(
        subject_id=subject_id,
        provider_subject=provider_subject,
        grant=_grant(
            provider_subject=provider_subject,
            refresh_token="old-refresh-token",
        ),
        repository=account_repository,
    )

    with pytest.raises(RuntimeError, match="requires access and refresh tokens"):
        await _bind_account_with_grant(
            subject_id=subject_id,
            provider_subject=provider_subject,
            grant=_grant(
                provider_subject=provider_subject,
                refresh_token=None,
            ),
            repository=account_repository,
        )

    async with build_session_factory(TEST_DATABASE_URL)() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT generation, revocation_status, encrypted_refresh_token
                    FROM apple_provider_grants
                    WHERE account_subject = :subject_id
                    """
                ),
                {"subject_id": subject_id},
            )
        ).all()

    assert len(rows) == 1
    assert rows[0].generation == 1
    assert rows[0].revocation_status == "active"
    assert rows[0].encrypted_refresh_token is not None

    claims = await provider_repository.claim_apple_provider_revocations(
        lease_owner="test-worker",
        limit=10,
    )
    assert claims == []


@pytest.mark.asyncio
async def test_binding_after_freeze_cannot_replace_apple_grant() -> None:
    await _reset_database()
    subject_id = uuid4()
    provider_subject = "apple-sub-frozen-no-replace"
    account_repository = _account_repository()
    await _bind_account_with_grant(
        subject_id=subject_id,
        provider_subject=provider_subject,
        grant=_grant(
            provider_subject=provider_subject,
            refresh_token="original-refresh-token",
        ),
        repository=account_repository,
    )
    await account_repository.accept_account_deletion(subject_id, reason="account_deletion")

    with pytest.raises(SubjectDeletedError):
        await _bind_account_with_grant(
            subject_id=subject_id,
            provider_subject=provider_subject,
            grant=_grant(
                provider_subject=provider_subject,
                refresh_token="replacement-refresh-token",
            ),
            repository=account_repository,
        )

    async with build_session_factory(TEST_DATABASE_URL)() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT generation, revocation_status, encrypted_refresh_token
                    FROM apple_provider_grants
                    WHERE account_subject = :subject_id
                    """
                ),
                {"subject_id": subject_id},
            )
        ).one()
    assert row.generation == 1
    assert row.revocation_status == "pending"
    assert row.encrypted_refresh_token is not None


@pytest.mark.asyncio
async def test_unreadable_ciphertext_records_revocation_failure() -> None:
    await _reset_database()
    subject_id = uuid4()
    sessions = build_session_factory(TEST_DATABASE_URL)
    provider_grants = _provider_repository()
    await _bind_account_with_grant(subject_id=subject_id)
    async with sessions() as session:
        await session.execute(
            text(
                """
                UPDATE apple_provider_grants
                SET encrypted_refresh_token = 'not-fernet-ciphertext'
                WHERE account_subject = :subject_id
                """
            ),
            {"subject_id": subject_id},
        )
        await session.commit()
    app = AccountApplication(
        repository=SqlAlchemyAccountRepository(
            sessions,
            apple_provider_grant_cipher=AppleProviderGrantCipher(ENCRYPTION_KEY),
        ),
        apple_identity=_UnusedAppleVerifier(),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="account-session-secret-with-enough-entropy",
        apple_provider_grants=provider_grants,
        apple_provider_revoker=_RecordingAppleRevoker([]),
        now=lambda: ISSUED_AT,
    )

    deletion = await app.request_account_deletion(subject_id)
    await app.process_apple_provider_revocations(lease_owner="test-worker")

    async with sessions() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT revocation_status, revocation_failure_code
                    FROM apple_provider_grants
                    WHERE account_subject = :subject_id
                    """
                ),
                {"subject_id": subject_id},
            )
        ).one()
    assert deletion.status == "frozen"
    assert row.revocation_status == "failed"
    assert row.revocation_failure_code == "apple_grant_unreadable"


@pytest.mark.asyncio
async def test_account_deletion_freezes_sqlalchemy_sessions_before_apple_io() -> None:
    await _reset_database()
    events: list[tuple[str, UUID | str]] = []
    sessions = build_session_factory(TEST_DATABASE_URL)
    account_repository = _RecordingSqlAlchemyAccountRepository(sessions, events)
    provider_grants = SqlAlchemyAppleProviderGrantRepository(
        sessions,
        cipher=AppleProviderGrantCipher(ENCRYPTION_KEY),
    )
    app = AccountApplication(
        repository=account_repository,
        apple_identity=_StaticAppleVerifier(),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="account-session-secret-with-enough-entropy",
        apple_provider_grants=provider_grants,
        apple_provider_revoker=_RecordingAppleRevoker(events),
        now=lambda: ISSUED_AT,
    )
    session = await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=uuid4(),
            identity_token="valid",
            authorization_code="single-use-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )

    await app.request_account_deletion(session.account_subject)

    apple_revocation = ("apple", "apple-refresh-token-for-revocation")
    local_session_revocation = ("stylecapture_sessions", session.account_subject)
    assert apple_revocation not in events
    await app.process_apple_provider_revocations(lease_owner="test-worker")
    assert events.index(("tombstone", session.account_subject)) < events.index(apple_revocation)
    assert events.index(local_session_revocation) < events.index(apple_revocation)


@pytest.mark.asyncio
async def test_account_deletion_records_sqlalchemy_apple_failure_after_freeze() -> None:
    await _reset_database()
    events: list[tuple[str, UUID | str]] = []
    sessions = build_session_factory(TEST_DATABASE_URL)
    account_repository = _RecordingSqlAlchemyAccountRepository(sessions, events)
    provider_grants = SqlAlchemyAppleProviderGrantRepository(
        sessions,
        cipher=AppleProviderGrantCipher(ENCRYPTION_KEY),
    )
    app = AccountApplication(
        repository=account_repository,
        apple_identity=_StaticAppleVerifier(),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="account-session-secret-with-enough-entropy",
        apple_provider_grants=provider_grants,
        apple_provider_revoker=_RecordingAppleRevoker(events, fail=True),
        now=lambda: ISSUED_AT,
    )
    session = await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=uuid4(),
            identity_token="valid",
            authorization_code="single-use-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )

    deletion = await app.request_account_deletion(session.account_subject)
    await app.process_apple_provider_revocations(lease_owner="test-worker")

    async with sessions() as db:
        row = (
            await db.execute(
                text(
                    """
                    SELECT revocation_status, revocation_failure_code
                    FROM apple_provider_grants
                    WHERE account_subject = :subject_id
                    """
                ),
                {"subject_id": session.account_subject},
            )
        ).one()
    assert deletion.status == "frozen"
    assert row.revocation_status == "failed"
    assert row.revocation_failure_code == "apple_revocation_failed"
    assert ("stylecapture_sessions", session.account_subject) in events


@pytest.mark.asyncio
async def test_pyjwt_verifier_provider_grant_reaches_sqlalchemy_persistence() -> None:
    await _reset_database()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = ISSUED_AT
    identity_token = _identity_token(
        key,
        iss="https://appleid.apple.com",
        aud="com.stylecapture.journey",
        sub="apple-sub-pyjwt-persisted",
        exp=now.replace(hour=1, minute=5),
        iat=now,
        nonce=hash_nonce("nonce-1"),
    )
    sessions = build_session_factory(TEST_DATABASE_URL)
    app = AccountApplication(
        repository=SqlAlchemyAccountRepository(
            sessions,
            apple_provider_grant_cipher=AppleProviderGrantCipher(ENCRYPTION_KEY),
        ),
        apple_identity=PyJWTAppleIdentityVerifier(
            jwks=_StaticJWKProvider([AppleJWK.from_public_key("kid-1", key.public_key())]),
            authorization_codes=_StaticAuthorizationCodeExchange(
                AppleAuthorizationGrant(
                    identity_token=identity_token,
                    access_token="apple-access-token-from-pyjwt",
                    refresh_token="apple-refresh-token-from-pyjwt",
                )
            ),
            allowed_audiences=frozenset({"com.stylecapture.journey"}),
            now=lambda: now,
        ),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="account-session-secret-with-enough-entropy",
        apple_provider_grants=SqlAlchemyAppleProviderGrantRepository(
            sessions,
            cipher=AppleProviderGrantCipher(ENCRYPTION_KEY),
        ),
        now=lambda: now,
    )

    tokens = await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=uuid4(),
            identity_token=identity_token,
            authorization_code="single-use-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )

    expected_subject = uuid5(NAMESPACE_URL, "stylecapture:apple:apple-sub-pyjwt-persisted")
    assert tokens.account_subject == expected_subject
    async with sessions() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT provider_subject, revocation_status
                    FROM apple_provider_grants
                    WHERE account_subject = :subject_id
                    """
                ),
                {"subject_id": expected_subject},
            )
        ).one()
    assert row.provider_subject == "apple-sub-pyjwt-persisted"
    assert row.revocation_status == "active"


@pytest.mark.asyncio
async def test_grant_write_failure_rolls_back_identity_binding_and_auth_code() -> None:
    await _reset_database()
    repository = SqlAlchemyAccountRepository(build_session_factory(TEST_DATABASE_URL))
    account_subject = uuid4()

    with pytest.raises(RuntimeError, match="grant encryption is not configured"):
        await repository.bind_apple_identity(
            anonymous_subject=uuid4(),
            identity=ExternalIdentity(
                provider="apple",
                provider_subject="apple-sub-grant-write-fails",
                account_subject=account_subject,
                created_at=ISSUED_AT,
            ),
            authorization_code_hash="f" * 64,
            account=Account(subject_id=account_subject, created_at=ISSUED_AT),
            apple_provider_grant=_grant(provider_subject="apple-sub-grant-write-fails"),
        )

    async with build_session_factory(TEST_DATABASE_URL)() as session:
        counts = (
            await session.execute(
                text(
                    """
                    SELECT
                        (SELECT count(*) FROM apple_authorization_codes) AS codes,
                        (SELECT count(*) FROM external_identities) AS identities,
                        (SELECT count(*) FROM accounts) AS accounts,
                        (SELECT count(*) FROM apple_provider_grants) AS grants
                    """
                )
            )
        ).one()
    assert counts.codes == 0
    assert counts.identities == 0
    assert counts.accounts == 0
    assert counts.grants == 0


def test_apple_provider_grants_migration_is_current_head_and_matches_model() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    config = Config(str(repository_root / "services" / "backend" / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    table = AppleProviderGrantRecord.__table__

    assert script.get_current_head() == "20260728_0018"
    assert set(table.columns.keys()) == {
        "id",
        "provider",
        "provider_subject",
        "account_subject",
        "generation",
        "encrypted_access_token",
        "encrypted_refresh_token",
        "created_at",
        "updated_at",
        "revoked_at",
        "revocation_status",
        "revocation_attempted_at",
        "revocation_failure_code",
        "revocation_attempt_count",
        "revocation_lease_owner",
        "revocation_lease_expires_at",
    }
    access_type = cast(String, table.c.encrypted_access_token.type)
    refresh_type = cast(String, table.c.encrypted_refresh_token.type)
    assert access_type.length == 4096
    assert refresh_type.length == 4096


class _StaticAppleVerifier:
    async def verify(
        self,
        identity_token: str,
        authorization_code: str,
    ) -> AppleIdentityClaims:
        del identity_token, authorization_code
        return _claims_provider_grant()


class _UnusedAppleVerifier:
    async def verify(
        self,
        identity_token: str,
        authorization_code: str,
    ) -> AppleIdentityClaims:
        del identity_token, authorization_code
        raise AssertionError("verification is not used by this test")


class _RecordingSqlAlchemyAccountRepository(SqlAlchemyAccountRepository):
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        events: list[tuple[str, UUID | str]],
    ) -> None:
        super().__init__(
            sessions,
            apple_provider_grant_cipher=AppleProviderGrantCipher(ENCRYPTION_KEY),
        )
        self.events = events

    async def tombstone_subject(self, subject_id: UUID, *, reason: str) -> DeletionRequest:
        canonical = await self.resolve_subject(subject_id)
        self.events.append(("tombstone", canonical))
        return await super().tombstone_subject(subject_id, reason=reason)

    async def revoke_subject_sessions(self, subject_id: UUID) -> None:
        canonical = await self.resolve_subject(subject_id)
        self.events.append(("stylecapture_sessions", canonical))
        await super().revoke_subject_sessions(subject_id)

    async def accept_account_deletion(
        self,
        subject_id: UUID,
        *,
        reason: str,
        access_token_hash: str | None = None,
        idempotency_key_hash: str | None = None,
    ) -> AccountDeletionAcceptance:
        canonical = await self.resolve_subject(subject_id)
        result = await super().accept_account_deletion(
            subject_id,
            reason=reason,
            access_token_hash=access_token_hash,
            idempotency_key_hash=idempotency_key_hash,
        )
        self.events.append(("tombstone", canonical))
        self.events.append(("stylecapture_sessions", canonical))
        return result


class _RecordingAppleRevoker:
    def __init__(self, events: list[tuple[str, UUID | str]], *, fail: bool = False) -> None:
        self.events = events
        self.fail = fail

    async def revoke(self, *, token: str, token_type_hint: str) -> None:
        self.events.append(("apple", token))
        self.events.append(("apple_hint", token_type_hint))
        if self.fail:
            raise ProviderGrantRevocationError("Apple token revocation failed")


class _StaticAuthorizationCodeExchange:
    def __init__(self, grant: AppleAuthorizationGrant) -> None:
        self.grant = grant

    async def exchange(self, authorization_code: str) -> AppleAuthorizationGrant:
        del authorization_code
        return self.grant


class _StaticJWKProvider:
    def __init__(self, keys: list[AppleJWK]) -> None:
        self._keys = keys

    async def keys(self, *, force_refresh: bool = False) -> list[AppleJWK]:
        del force_refresh
        return self._keys


def _claims_provider_grant() -> AppleIdentityClaims:
    return AppleIdentityClaims(
        issuer="https://appleid.apple.com",
        audience="com.stylecapture.journey",
        subject="apple-sub-revocable",
        expires_at=datetime(2026, 7, 28, 1, 15, tzinfo=UTC),
        issued_at=ISSUED_AT,
        nonce=hash_nonce("nonce-1"),
        provider_grant=AppleProviderGrant(
            provider_subject="apple-sub-revocable",
            access_token="apple-access-token-for-revocation",
            refresh_token="apple-refresh-token-for-revocation",
            issued_at=ISSUED_AT,
        ),
    )


def _identity_token(
    private_key: rsa.RSAPrivateKey,
    *,
    kid: str = "kid-1",
    **claims: object,
) -> str:
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": kid, "alg": "RS256"},
    )
