from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from stylecapture_backend.features.account.domain import (
    Account,
    AccountBindingConflictError,
    AuthorizationCodeReplayError,
    ExternalIdentity,
    SubjectDeletedError,
)
from stylecapture_backend.features.account.infrastructure.repository import (
    SqlAlchemyAccountRepository,
)
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    JobState,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.infrastructure.repository import (
    SqlAlchemyCaptureRepository,
)
from stylecapture_backend.platform.database import build_session_factory, run_migrations

TEST_DATABASE_URL = os.environ.get(
    "STYLECAPTURE_TEST_DATABASE_URL",
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture_test",
)


async def _reset_database() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE apple_authorization_codes, used_refresh_tokens, "
                "apple_provider_grants, device_sessions, subject_aliases, "
                "external_identities, accounts, subject_tombstones, "
                "deletion_requests, captures CASCADE"
            )
        )
        await session.commit()


async def _insert_capture(subject_id: UUID) -> UUID:
    capture_id = uuid4()
    async with build_session_factory(TEST_DATABASE_URL)() as session:
        await session.execute(
            text(
                """
                INSERT INTO captures (
                    id, user_id, source_kind, object_key, sha256,
                    ownership, idempotency_key, created_at
                ) VALUES (
                    :capture_id, :user_id, 'upload', :object_key, :sha256,
                    'owned', :idempotency_key, :created_at
                )
                """
            ),
            {
                "capture_id": capture_id,
                "user_id": subject_id,
                "object_key": f"originals/account-binding/{capture_id}.png",
                "sha256": "a" * 64,
                "idempotency_key": f"account-binding-{capture_id}",
                "created_at": datetime.now(UTC),
            },
        )
        await session.commit()
    return capture_id


def _binding(*, provider_subject: str, account_subject: UUID) -> tuple[ExternalIdentity, Account]:
    now = datetime.now(UTC)
    return (
        ExternalIdentity(
            provider="apple",
            provider_subject=provider_subject,
            account_subject=account_subject,
            created_at=now,
        ),
        Account(subject_id=account_subject, created_at=now),
    )


@pytest.mark.asyncio
async def test_concurrent_different_apple_bindings_allow_only_one_canonical_owner() -> None:
    await _reset_database()
    anonymous_subject = uuid4()
    capture_id = await _insert_capture(anonymous_subject)
    sessions = build_session_factory(TEST_DATABASE_URL)
    repository = SqlAlchemyAccountRepository(sessions)
    first_identity, first_account = _binding(
        provider_subject="apple-sub-first",
        account_subject=uuid4(),
    )
    second_identity, second_account = _binding(
        provider_subject="apple-sub-second",
        account_subject=uuid4(),
    )

    results = await asyncio.gather(
        repository.bind_apple_identity(
            anonymous_subject=anonymous_subject,
            identity=first_identity,
            authorization_code_hash="1" * 64,
            account=first_account,
        ),
        repository.bind_apple_identity(
            anonymous_subject=anonymous_subject,
            identity=second_identity,
            authorization_code_hash="2" * 64,
            account=second_account,
        ),
        return_exceptions=True,
    )

    accounts = [result for result in results if isinstance(result, Account)]
    conflicts = [result for result in results if isinstance(result, AccountBindingConflictError)]
    assert len(accounts) == 1
    assert len(conflicts) == 1
    canonical = accounts[0].subject_id
    assert await repository.resolve_subject(anonymous_subject) == canonical
    async with sessions() as session:
        capture_owner = await session.scalar(
            text("SELECT user_id FROM captures WHERE id = :capture_id"),
            {"capture_id": capture_id},
        )
        identity_count = await session.scalar(text("SELECT count(*) FROM external_identities"))
    assert capture_owner == canonical
    assert identity_count == 1


@pytest.mark.asyncio
async def test_concurrent_replay_is_typed_and_does_not_move_losing_ownership() -> None:
    await _reset_database()
    first_subject = uuid4()
    second_subject = uuid4()
    first_capture = await _insert_capture(first_subject)
    second_capture = await _insert_capture(second_subject)
    sessions = build_session_factory(TEST_DATABASE_URL)
    repository = SqlAlchemyAccountRepository(sessions)
    first_identity, first_account = _binding(
        provider_subject="apple-sub-replay-first",
        account_subject=uuid4(),
    )
    second_identity, second_account = _binding(
        provider_subject="apple-sub-replay-second",
        account_subject=uuid4(),
    )

    results = await asyncio.gather(
        repository.bind_apple_identity(
            anonymous_subject=first_subject,
            identity=first_identity,
            authorization_code_hash="a" * 64,
            account=first_account,
        ),
        repository.bind_apple_identity(
            anonymous_subject=second_subject,
            identity=second_identity,
            authorization_code_hash="a" * 64,
            account=second_account,
        ),
        return_exceptions=True,
    )

    assert len([result for result in results if isinstance(result, Account)]) == 1
    assert (
        len([result for result in results if isinstance(result, AuthorizationCodeReplayError)]) == 1
    )
    losing_capture, losing_subject = (
        (first_capture, first_subject)
        if isinstance(results[0], AuthorizationCodeReplayError)
        else (second_capture, second_subject)
    )
    async with sessions() as session:
        losing_owner = await session.scalar(
            text("SELECT user_id FROM captures WHERE id = :capture_id"),
            {"capture_id": losing_capture},
        )
        code_count = await session.scalar(text("SELECT count(*) FROM apple_authorization_codes"))
    assert losing_owner == losing_subject
    assert code_count == 1


@pytest.mark.asyncio
async def test_concurrent_same_apple_identity_unifies_both_anonymous_owners() -> None:
    await _reset_database()
    first_subject = uuid4()
    second_subject = uuid4()
    first_capture = await _insert_capture(first_subject)
    second_capture = await _insert_capture(second_subject)
    canonical_subject = uuid4()
    first_identity, first_account = _binding(
        provider_subject="apple-sub-shared",
        account_subject=canonical_subject,
    )
    second_identity, second_account = _binding(
        provider_subject="apple-sub-shared",
        account_subject=canonical_subject,
    )
    sessions = build_session_factory(TEST_DATABASE_URL)
    repository = SqlAlchemyAccountRepository(sessions)

    first, second = await asyncio.gather(
        repository.bind_apple_identity(
            anonymous_subject=first_subject,
            identity=first_identity,
            authorization_code_hash="b" * 64,
            account=first_account,
        ),
        repository.bind_apple_identity(
            anonymous_subject=second_subject,
            identity=second_identity,
            authorization_code_hash="c" * 64,
            account=second_account,
        ),
    )

    assert first.subject_id == second.subject_id == canonical_subject
    async with sessions() as session:
        owners = (
            (
                await session.execute(
                    text(
                        "SELECT user_id FROM captures WHERE id IN (:first_capture, :second_capture)"
                    ),
                    {
                        "first_capture": first_capture,
                        "second_capture": second_capture,
                    },
                )
            )
            .scalars()
            .all()
        )
        identity_count = await session.scalar(text("SELECT count(*) FROM external_identities"))
    assert owners == [canonical_subject, canonical_subject]
    assert identity_count == 1


@pytest.mark.asyncio
async def test_binding_to_deleted_existing_identity_does_not_move_anonymous_ownership() -> None:
    await _reset_database()
    canonical_subject = uuid4()
    first_subject = uuid4()
    second_subject = uuid4()
    identity, account = _binding(
        provider_subject="apple-sub-deleted",
        account_subject=canonical_subject,
    )
    sessions = build_session_factory(TEST_DATABASE_URL)
    repository = SqlAlchemyAccountRepository(sessions)
    await repository.bind_apple_identity(
        anonymous_subject=first_subject,
        identity=identity,
        authorization_code_hash="d" * 64,
        account=account,
    )
    await repository.tombstone_subject(canonical_subject, reason="account_deletion")
    capture_id = await _insert_capture(second_subject)

    with pytest.raises(SubjectDeletedError):
        await repository.bind_apple_identity(
            anonymous_subject=second_subject,
            identity=identity,
            authorization_code_hash="e" * 64,
            account=account,
        )

    async with sessions() as session:
        capture_owner = await session.scalar(
            text("SELECT user_id FROM captures WHERE id = :capture_id"),
            {"capture_id": capture_id},
        )
        code_count = await session.scalar(text("SELECT count(*) FROM apple_authorization_codes"))
    assert capture_owner == second_subject
    assert code_count == 1


@pytest.mark.asyncio
async def test_subject_write_lease_serializes_deletion_and_rejects_late_work() -> None:
    await _reset_database()
    subject_id = uuid4()
    identity, account = _binding(
        provider_subject="apple-sub-write-lease",
        account_subject=subject_id,
    )
    repository = SqlAlchemyAccountRepository(build_session_factory(TEST_DATABASE_URL))
    await repository.bind_apple_identity(
        anonymous_subject=uuid4(),
        identity=identity,
        authorization_code_hash="f" * 64,
        account=account,
    )

    async with repository.subject_write(subject_id) as canonical:
        deletion = asyncio.create_task(
            repository.tombstone_subject(subject_id, reason="account_deletion")
        )
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(deletion), timeout=0.05)
        assert canonical == subject_id

    deleted = await deletion
    assert deleted.subject_id == subject_id
    with pytest.raises(SubjectDeletedError):
        async with repository.subject_write(subject_id):
            pytest.fail("deleted subjects must never receive a write lease")


@pytest.mark.asyncio
async def test_capture_repository_rejects_new_submission_after_tombstone() -> None:
    await _reset_database()
    subject_id = uuid4()
    identity, account = _binding(
        provider_subject="apple-sub-deleted-capture",
        account_subject=subject_id,
    )
    sessions = build_session_factory(TEST_DATABASE_URL)
    accounts = SqlAlchemyAccountRepository(sessions)
    await accounts.bind_apple_identity(
        anonymous_subject=uuid4(),
        identity=identity,
        authorization_code_hash="9" * 64,
        account=account,
    )
    await accounts.tombstone_subject(subject_id, reason="account_deletion")
    capture = Capture.create(
        user_id=subject_id,
        source=CaptureSource(
            kind=CaptureSourceKind.UPLOAD,
            object_key=f"originals/deleted/{uuid4()}.png",
            sha256="9" * 64,
        ),
        ownership=OwnershipState.OWNED,
    )
    job = ProcessingJob.queued(capture_id=capture.id)

    with pytest.raises(SubjectDeletedError):
        await SqlAlchemyCaptureRepository(sessions).save_submission(
            capture,
            job,
            "deleted-capture-submission",
        )

    async with sessions() as session:
        capture_count = await session.scalar(text("SELECT count(*) FROM captures"))
    assert capture_count == 0


@pytest.mark.asyncio
async def test_capture_repository_rejects_late_job_finalization_after_tombstone() -> None:
    await _reset_database()
    subject_id = uuid4()
    identity, account = _binding(
        provider_subject="apple-sub-deleted-job",
        account_subject=subject_id,
    )
    sessions = build_session_factory(TEST_DATABASE_URL)
    accounts = SqlAlchemyAccountRepository(sessions)
    await accounts.bind_apple_identity(
        anonymous_subject=uuid4(),
        identity=identity,
        authorization_code_hash="8" * 64,
        account=account,
    )
    capture = Capture.create(
        user_id=subject_id,
        source=CaptureSource(
            kind=CaptureSourceKind.UPLOAD,
            object_key=f"originals/deleted-job/{uuid4()}.png",
            sha256="8" * 64,
        ),
        ownership=OwnershipState.OWNED,
    )
    job = ProcessingJob.queued(capture_id=capture.id)
    captures = SqlAlchemyCaptureRepository(sessions)
    await captures.save_submission(capture, job, "deleted-job-submission")
    await accounts.tombstone_subject(subject_id, reason="account_deletion")

    with pytest.raises(SubjectDeletedError):
        await captures.update(job.transition(target=JobState.PROCESSING))

    stored = await captures.get_job(job.id)
    assert stored is not None
    assert stored.state == job.state
