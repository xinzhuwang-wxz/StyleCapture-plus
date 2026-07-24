from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    CaptureError,
    SubmitCaptureCommand,
)
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSourceKind,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.ports import (
    CaptureRepository,
    CaptureSubmission,
    JobDispatcher,
    JobDispatchError,
    StoredObject,
)


class MemoryCaptureRepository(CaptureRepository):
    def __init__(self) -> None:
        self.submissions: dict[tuple[UUID, str], CaptureSubmission] = {}

    async def find_by_idempotency(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> CaptureSubmission | None:
        return self.submissions.get((user_id, idempotency_key))

    async def save_submission(
        self,
        capture: Capture,
        job: ProcessingJob,
        idempotency_key: str,
    ) -> CaptureSubmission:
        submission = CaptureSubmission(capture=capture, job=job)
        self.submissions[(capture.user_id, idempotency_key)] = submission
        return submission


class RecordingDispatcher(JobDispatcher):
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID]] = []

    def enqueue_capture(self, capture_id: UUID, job_id: UUID) -> None:
        self.calls.append((capture_id, job_id))


class FlakyDispatcher(JobDispatcher):
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID]] = []

    def enqueue_capture(self, capture_id: UUID, job_id: UUID) -> None:
        self.calls.append((capture_id, job_id))
        if len(self.calls) == 1:
            raise JobDispatchError("broker unavailable")


@dataclass(frozen=True)
class StoredObjectLookup:
    objects: Mapping[str, StoredObject]

    def describe(self, object_key: str) -> StoredObject:
        return self.objects[object_key]


@pytest.mark.asyncio
async def test_submit_creates_capture_and_dispatches_one_durable_job() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/u/garment.png",
        content_type="image/png",
        byte_size=123,
        sha256="c" * 64,
        width=640,
        height=960,
    )
    repository = MemoryCaptureRepository()
    dispatcher = RecordingDispatcher()
    application = CaptureApplication(
        captures=repository,
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=dispatcher,
    )

    submission = await application.submit(
        SubmitCaptureCommand(
            user_id=user_id,
            object_key=stored.object_key,
            sha256=stored.sha256,
            source_kind=CaptureSourceKind.CAMERA,
            ownership=OwnershipState.OWNED,
            idempotency_key="mobile-request-001",
        )
    )

    assert submission.capture.source.object_key == stored.object_key
    assert submission.capture.source.kind is CaptureSourceKind.CAMERA
    assert submission.capture.ownership is OwnershipState.OWNED
    assert dispatcher.calls == [(submission.capture.id, submission.job.id)]


@pytest.mark.asyncio
async def test_repeated_idempotency_key_returns_original_and_redrives_the_job() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/u/inspiration.webp",
        content_type="image/webp",
        byte_size=456,
        sha256="d" * 64,
        width=800,
        height=800,
    )
    repository = MemoryCaptureRepository()
    dispatcher = RecordingDispatcher()
    application = CaptureApplication(
        captures=repository,
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=dispatcher,
    )
    command = SubmitCaptureCommand(
        user_id=user_id,
        object_key=stored.object_key,
        sha256=stored.sha256,
        source_kind=CaptureSourceKind.UPLOAD,
        ownership=OwnershipState.INSPIRATION,
        idempotency_key="mobile-request-002",
    )

    first = await application.submit(command)
    second = await application.submit(command)

    assert second == first
    assert dispatcher.calls == [
        (first.capture.id, first.job.id),
        (first.capture.id, first.job.id),
    ]


@pytest.mark.asyncio
async def test_broker_failure_retains_the_capture_for_idempotent_redrive() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/u/retry.png",
        content_type="image/png",
        byte_size=123,
        sha256="e" * 64,
        width=640,
        height=960,
    )
    repository = MemoryCaptureRepository()
    dispatcher = FlakyDispatcher()
    application = CaptureApplication(
        captures=repository,
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=dispatcher,
    )
    command = SubmitCaptureCommand(
        user_id=user_id,
        object_key=stored.object_key,
        sha256=stored.sha256,
        source_kind=CaptureSourceKind.UPLOAD,
        ownership=OwnershipState.OWNED,
        idempotency_key="mobile-request-redrive",
    )

    with pytest.raises(CaptureError) as first_error:
        await application.submit(command)
    recovered = await application.submit(command)

    assert first_error.value.code == "processing_dispatch_unavailable"
    assert len(repository.submissions) == 1
    assert dispatcher.calls == [
        (recovered.capture.id, recovered.job.id),
        (recovered.capture.id, recovered.job.id),
    ]


@pytest.mark.asyncio
async def test_submit_cannot_claim_another_sessions_prepared_upload() -> None:
    owner_id = uuid4()
    stored = StoredObject(
        owner_id=owner_id,
        object_key="originals/u/private.png",
        content_type="image/png",
        byte_size=123,
        sha256="f" * 64,
        width=640,
        height=960,
    )
    application = CaptureApplication(
        captures=MemoryCaptureRepository(),
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=RecordingDispatcher(),
    )

    with pytest.raises(CaptureError) as error:
        await application.submit(
            SubmitCaptureCommand(
                user_id=uuid4(),
                object_key=stored.object_key,
                sha256=stored.sha256,
                source_kind=CaptureSourceKind.UPLOAD,
                ownership=OwnershipState.INSPIRATION,
                idempotency_key="cross-session-claim",
            )
        )

    assert error.value.code == "upload_not_found"
