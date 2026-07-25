from __future__ import annotations

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
    FeedCaptureIntent,
    FeedFrameContext,
    FeedSelection,
    NormalizedPoint,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.ports import (
    CaptureRepository,
    CaptureSubmission,
    JobDispatcher,
    StoredObject,
    WholeOutfitRegistrar,
)
from stylecapture_backend.features.look.ports import LookPersistenceUnavailable


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


class MemoryWholeOutfitRegistrar(WholeOutfitRegistrar):
    def __init__(self, events: list[str] | None = None) -> None:
        self.looks: dict[UUID, PendingLookReference] = {}
        self.calls: list[tuple[UUID, str]] = []
        self.events = events

    async def ensure_saved_look(
        self,
        capture: Capture,
        *,
        idempotency_key: str,
    ) -> PendingLookReference:
        self.calls.append((capture.id, idempotency_key))
        if self.events is not None:
            self.events.append("look")
        return self.looks.setdefault(capture.id, PendingLookReference(id=uuid4()))


@dataclass(frozen=True)
class PendingLookReference:
    id: UUID


@dataclass(frozen=True)
class StoredObjectLookup:
    objects: Mapping[str, StoredObject]

    def describe(self, object_key: str) -> StoredObject:
        return self.objects[object_key]


def feed_context() -> FeedFrameContext:
    return FeedFrameContext(
        video_ref="feed://demo/look-001",
        timestamp_ms=4_200,
        frame_width=1080,
        frame_height=1920,
        selections=(
            FeedSelection(
                selection_key="hat",
                polygon=(
                    NormalizedPoint(x=0.35, y=0.08),
                    NormalizedPoint(x=0.54, y=0.09),
                    NormalizedPoint(x=0.49, y=0.23),
                ),
            ),
            FeedSelection(
                selection_key="jacket",
                polygon=(
                    NormalizedPoint(x=0.28, y=0.28),
                    NormalizedPoint(x=0.68, y=0.30),
                    NormalizedPoint(x=0.63, y=0.67),
                    NormalizedPoint(x=0.31, y=0.64),
                ),
            ),
        ),
    )


def whole_outfit_context() -> FeedFrameContext:
    selection = feed_context().selections[1]
    return FeedFrameContext(
        video_ref="feed://demo/look-001",
        timestamp_ms=4_200,
        frame_width=1080,
        frame_height=1920,
        selections=(selection,),
        intent=FeedCaptureIntent.WHOLE_OUTFIT,
    )


@pytest.mark.parametrize(
    ("x", "y"),
    [
        (-0.01, 0.5),
        (1.01, 0.5),
        (0.5, float("nan")),
        (float("inf"), 0.5),
    ],
)
def test_normalized_point_rejects_coordinates_outside_the_frame(x: float, y: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        NormalizedPoint(x=x, y=y)


@pytest.mark.parametrize(
    "polygon",
    [
        (NormalizedPoint(0.1, 0.1), NormalizedPoint(0.2, 0.2)),
        (
            NormalizedPoint(0.1, 0.1),
            NormalizedPoint(0.1, 0.1),
            NormalizedPoint(0.2, 0.2),
        ),
    ],
)
def test_feed_selection_requires_three_unique_polygon_points(
    polygon: tuple[NormalizedPoint, ...],
) -> None:
    with pytest.raises(ValueError, match="3 unique points"):
        FeedSelection(selection_key="garment", polygon=polygon)


def test_feed_frame_rejects_duplicate_selection_keys() -> None:
    selection = FeedSelection(
        selection_key="garment",
        polygon=(
            NormalizedPoint(0.1, 0.1),
            NormalizedPoint(0.3, 0.1),
            NormalizedPoint(0.2, 0.3),
        ),
    )

    with pytest.raises(ValueError, match="selection keys must be unique"):
        FeedFrameContext(
            video_ref="feed://demo/look-duplicate",
            timestamp_ms=10,
            frame_width=1080,
            frame_height=1920,
            selections=(selection, selection),
        )


def test_feed_frame_limits_one_save_gesture_to_eight_selections() -> None:
    selections = tuple(
        FeedSelection(
            selection_key=f"garment-{index}",
            polygon=(
                NormalizedPoint(0.1, 0.1),
                NormalizedPoint(0.3, 0.1),
                NormalizedPoint(0.2, 0.3),
            ),
        )
        for index in range(9)
    )

    with pytest.raises(ValueError, match="between 1 and 8 selections"):
        FeedFrameContext(
            video_ref="feed://demo/look-too-many",
            timestamp_ms=10,
            frame_width=1080,
            frame_height=1920,
            selections=selections,
        )


@pytest.mark.asyncio
async def test_feed_submit_keeps_multiple_selections_in_one_durable_job() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/feed/frame-001.webp",
        content_type="image/webp",
        byte_size=456,
        sha256="d" * 64,
        width=1080,
        height=1920,
    )
    repository = MemoryCaptureRepository()
    dispatcher = RecordingDispatcher()
    application = CaptureApplication(
        captures=repository,
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=dispatcher,
    )
    context = feed_context()

    submission = await application.submit(
        SubmitCaptureCommand(
            user_id=user_id,
            object_key=stored.object_key,
            sha256=stored.sha256,
            source_kind=CaptureSourceKind.FEED,
            ownership=OwnershipState.INSPIRATION,
            idempotency_key="feed-frame-001",
            feed_context=context,
        )
    )

    assert submission.capture.feed_context == context
    assert submission.capture.source.origin_ref == context.video_ref
    assert len(submission.capture.feed_context.selections) == 2
    assert dispatcher.calls == [(submission.capture.id, submission.job.id)]


@pytest.mark.asyncio
async def test_feed_submit_reuses_the_original_selection_batch_on_network_retry() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/feed/frame-002.webp",
        content_type="image/webp",
        byte_size=456,
        sha256="e" * 64,
        width=1080,
        height=1920,
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
        source_kind=CaptureSourceKind.FEED,
        ownership=OwnershipState.INSPIRATION,
        idempotency_key="feed-frame-002",
        feed_context=feed_context(),
    )

    first = await application.submit(command)
    second = await application.submit(command)

    assert second == first
    assert len(repository.submissions) == 1
    assert dispatcher.calls == [
        (first.capture.id, first.job.id),
        (first.capture.id, first.job.id),
    ]


@pytest.mark.asyncio
async def test_whole_outfit_submit_ensures_pending_look_before_dispatch() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/feed/whole-look.webp",
        content_type="image/webp",
        byte_size=456,
        sha256="9" * 64,
        width=1080,
        height=1920,
    )
    repository = MemoryCaptureRepository()
    events: list[str] = []
    registrar = MemoryWholeOutfitRegistrar(events)

    class OrderedDispatcher(RecordingDispatcher):
        def enqueue_capture(self, capture_id: UUID, job_id: UUID) -> None:
            events.append("dispatch")
            super().enqueue_capture(capture_id, job_id)

    dispatcher = OrderedDispatcher()
    application = CaptureApplication(
        captures=repository,
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=dispatcher,
        whole_outfits=registrar,
    )

    submission = await application.submit(
        SubmitCaptureCommand(
            user_id=user_id,
            object_key=stored.object_key,
            sha256=stored.sha256,
            source_kind=CaptureSourceKind.FEED,
            ownership=OwnershipState.INSPIRATION,
            idempotency_key="feed-whole-look-001",
            feed_context=whole_outfit_context(),
        )
    )

    assert submission.look_id == registrar.looks[submission.capture.id].id
    assert events == ["look", "dispatch"]
    assert dispatcher.calls == [(submission.capture.id, submission.job.id)]


@pytest.mark.asyncio
async def test_whole_outfit_retry_repairs_pending_look_without_duplicate_identity() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/feed/whole-look-retry.webp",
        content_type="image/webp",
        byte_size=456,
        sha256="8" * 64,
        width=1080,
        height=1920,
    )
    repository = MemoryCaptureRepository()
    dispatcher = RecordingDispatcher()
    registrar = MemoryWholeOutfitRegistrar()
    application = CaptureApplication(
        captures=repository,
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=dispatcher,
        whole_outfits=registrar,
    )
    command = SubmitCaptureCommand(
        user_id=user_id,
        object_key=stored.object_key,
        sha256=stored.sha256,
        source_kind=CaptureSourceKind.FEED,
        ownership=OwnershipState.INSPIRATION,
        idempotency_key="feed-whole-look-retry",
        feed_context=whole_outfit_context(),
    )

    first = await application.submit(command)
    second = await application.submit(command)

    assert second.capture.id == first.capture.id
    assert second.job.id == first.job.id
    assert second.look_id == first.look_id
    assert registrar.calls == [
        (first.capture.id, "feed-whole-look-retry"),
        (first.capture.id, "feed-whole-look-retry"),
    ]
    assert len(registrar.looks) == 1


@pytest.mark.asyncio
async def test_whole_outfit_without_registrar_keeps_capture_safe_and_does_not_dispatch() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/feed/whole-look-unwired.webp",
        content_type="image/webp",
        byte_size=456,
        sha256="7" * 64,
        width=1080,
        height=1920,
    )
    repository = MemoryCaptureRepository()
    dispatcher = RecordingDispatcher()
    application = CaptureApplication(
        captures=repository,
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=dispatcher,
    )

    with pytest.raises(CaptureError) as error:
        await application.submit(
            SubmitCaptureCommand(
                user_id=user_id,
                object_key=stored.object_key,
                sha256=stored.sha256,
                source_kind=CaptureSourceKind.FEED,
                ownership=OwnershipState.INSPIRATION,
                idempotency_key="feed-whole-look-unwired",
                feed_context=whole_outfit_context(),
            )
        )

    assert error.value.code == "look_registration_unavailable"
    assert len(repository.submissions) == 1
    assert dispatcher.calls == []


@pytest.mark.asyncio
async def test_whole_outfit_programming_error_is_not_misreported_as_retryable() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/feed/whole-look-invariant.webp",
        content_type="image/webp",
        byte_size=456,
        sha256="6" * 64,
        width=1080,
        height=1920,
    )

    class BrokenRegistrar(WholeOutfitRegistrar):
        async def ensure_saved_look(
            self,
            capture: Capture,
            *,
            idempotency_key: str,
        ) -> PendingLookReference:
            raise AssertionError("programming invariant failed")

    repository = MemoryCaptureRepository()
    dispatcher = RecordingDispatcher()
    application = CaptureApplication(
        captures=repository,
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=dispatcher,
        whole_outfits=BrokenRegistrar(),
    )

    with pytest.raises(AssertionError, match="programming invariant failed"):
        await application.submit(
            SubmitCaptureCommand(
                user_id=user_id,
                object_key=stored.object_key,
                sha256=stored.sha256,
                source_kind=CaptureSourceKind.FEED,
                ownership=OwnershipState.INSPIRATION,
                idempotency_key="feed-whole-look-invariant",
                feed_context=whole_outfit_context(),
            )
        )

    assert len(repository.submissions) == 1
    assert dispatcher.calls == []


@pytest.mark.asyncio
async def test_whole_outfit_persistence_unavailable_remains_retryable() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/feed/whole-look-store-unavailable.webp",
        content_type="image/webp",
        byte_size=456,
        sha256="5" * 64,
        width=1080,
        height=1920,
    )

    class UnavailableRegistrar(WholeOutfitRegistrar):
        async def ensure_saved_look(
            self,
            capture: Capture,
            *,
            idempotency_key: str,
        ) -> PendingLookReference:
            raise LookPersistenceUnavailable("database unavailable")

    repository = MemoryCaptureRepository()
    dispatcher = RecordingDispatcher()
    application = CaptureApplication(
        captures=repository,
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=dispatcher,
        whole_outfits=UnavailableRegistrar(),
    )

    with pytest.raises(CaptureError) as error:
        await application.submit(
            SubmitCaptureCommand(
                user_id=user_id,
                object_key=stored.object_key,
                sha256=stored.sha256,
                source_kind=CaptureSourceKind.FEED,
                ownership=OwnershipState.INSPIRATION,
                idempotency_key="feed-whole-look-store-unavailable",
                feed_context=whole_outfit_context(),
            )
        )

    assert error.value.code == "look_registration_unavailable"
    assert error.value.details["retryable"] is True
    assert len(repository.submissions) == 1
    assert dispatcher.calls == []


@pytest.mark.asyncio
async def test_feed_submit_requires_selection_context() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/feed/frame-without-context.webp",
        content_type="image/webp",
        byte_size=456,
        sha256="f" * 64,
        width=1080,
        height=1920,
    )
    application = CaptureApplication(
        captures=MemoryCaptureRepository(),
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=RecordingDispatcher(),
    )

    with pytest.raises(CaptureError) as error:
        await application.submit(
            SubmitCaptureCommand(
                user_id=user_id,
                object_key=stored.object_key,
                sha256=stored.sha256,
                source_kind=CaptureSourceKind.FEED,
                ownership=OwnershipState.INSPIRATION,
                idempotency_key="feed-without-context",
            )
        )

    assert error.value.code == "feed_context_required"


@pytest.mark.asyncio
async def test_feed_submit_rejects_frame_dimensions_that_do_not_match_the_upload() -> None:
    user_id = uuid4()
    stored = StoredObject(
        owner_id=user_id,
        object_key="originals/feed/frame-dimensions.webp",
        content_type="image/webp",
        byte_size=456,
        sha256="a" * 64,
        width=720,
        height=1280,
    )
    application = CaptureApplication(
        captures=MemoryCaptureRepository(),
        objects=StoredObjectLookup({stored.object_key: stored}),
        dispatcher=RecordingDispatcher(),
    )

    with pytest.raises(CaptureError) as error:
        await application.submit(
            SubmitCaptureCommand(
                user_id=user_id,
                object_key=stored.object_key,
                sha256=stored.sha256,
                source_kind=CaptureSourceKind.FEED,
                ownership=OwnershipState.INSPIRATION,
                idempotency_key="feed-dimensions-mismatch",
                feed_context=feed_context(),
            )
        )

    assert error.value.code == "feed_frame_dimensions_mismatch"
