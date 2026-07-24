import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    FeedFrameContext,
    FeedSelection,
    JobState,
    NormalizedPoint,
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
    found_capture = await repository.get_capture(capture.id)
    found_job = await repository.get_job(job.id)
    processing = saved.job.transition(JobState.PROCESSING)
    await repository.update(processing)
    stored_job = await repository.get_for_user(job.id, user_id)

    assert found == saved
    assert found_capture == capture
    assert found_job == job
    assert stored_job == processing


@pytest.mark.asyncio
async def test_repository_round_trips_feed_origin_and_selection_batch() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE items, processing_jobs, captures CASCADE"))
        await session.commit()
    repository = SqlAlchemyCaptureRepository(sessions)
    user_id = uuid4()
    feed_context = FeedFrameContext(
        video_ref="feed://demo/repository-look",
        timestamp_ms=2_750,
        frame_width=720,
        frame_height=1280,
        selections=(
            FeedSelection(
                selection_key="top",
                polygon=(
                    NormalizedPoint(0.2, 0.2),
                    NormalizedPoint(0.7, 0.2),
                    NormalizedPoint(0.65, 0.6),
                    NormalizedPoint(0.25, 0.6),
                ),
            ),
            FeedSelection(
                selection_key="bag",
                polygon=(
                    NormalizedPoint(0.65, 0.55),
                    NormalizedPoint(0.84, 0.54),
                    NormalizedPoint(0.82, 0.76),
                ),
            ),
        ),
    )
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.FEED,
            object_key="originals/feed/repository-look.webp",
            sha256="b" * 64,
            origin_ref=feed_context.video_ref,
        ),
        ownership=OwnershipState.INSPIRATION,
        feed_context=feed_context,
    )
    job = ProcessingJob.queued(capture_id=capture.id)

    await repository.save_submission(capture, job, "feed-repository-001")
    found = await repository.find_by_idempotency(user_id, "feed-repository-001")

    assert found is not None
    assert found.capture == capture


def test_worker_session_factory_is_safe_across_sequential_event_loops() -> None:
    asyncio.run(run_migrations(TEST_DATABASE_URL))
    sessions = build_session_factory(TEST_DATABASE_URL, pooled=False)
    repository = SqlAlchemyCaptureRepository(sessions)
    capture = Capture.create(
        user_id=uuid4(),
        source=CaptureSource(
            kind=CaptureSourceKind.CAMERA,
            object_key=f"originals/worker-loops/{uuid4()}.png",
            sha256="a" * 64,
        ),
        ownership=OwnershipState.OWNED,
    )
    job = ProcessingJob.queued(capture_id=capture.id)

    asyncio.run(repository.save_submission(capture, job, f"worker-loop-{uuid4()}"))
    first = asyncio.run(repository.get_capture(capture.id))
    second = asyncio.run(repository.get_capture(capture.id))

    assert first == capture
    assert second == capture
