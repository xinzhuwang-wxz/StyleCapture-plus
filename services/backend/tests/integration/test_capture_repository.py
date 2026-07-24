import os
from uuid import uuid4

import pytest
from sqlalchemy import text
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
from stylecapture_backend.platform.database import (
    build_session_factory,
    run_migrations,
)

TEST_DATABASE_URL = os.environ.get(
    "STYLECAPTURE_TEST_DATABASE_URL",
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture",
)


@pytest.mark.asyncio
async def test_repository_round_trips_submission_idempotency_and_job_state() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE items, processing_jobs, captures CASCADE"))
        await session.commit()
    repository = SqlAlchemyCaptureRepository(sessions)
    user_id = uuid4()
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.UPLOAD,
            object_key="originals/2026/07/25/garment.png",
            sha256="e" * 64,
        ),
        ownership=OwnershipState.INSPIRATION,
    )
    job = ProcessingJob.queued(capture_id=capture.id)

    saved = await repository.save_submission(capture, job, "repo-idempotency-001")
    found = await repository.find_by_idempotency(user_id, "repo-idempotency-001")
    processing = saved.job.transition(JobState.PROCESSING)
    await repository.update(processing)
    stored_job = await repository.get_for_user(job.id, user_id)

    assert found == saved
    assert stored_job == processing
