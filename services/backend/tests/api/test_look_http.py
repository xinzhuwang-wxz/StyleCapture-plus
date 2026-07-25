from __future__ import annotations

from dataclasses import replace
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    FeedCaptureIntent,
    FeedFrameContext,
    FeedSelection,
    JobState,
    NormalizedPoint,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.ports import (
    CaptureRepository,
    JobDispatcher,
    JobRepository,
    ObjectStore,
    StoredObject,
)
from stylecapture_backend.features.look.application import LookApplication
from stylecapture_backend.features.look.domain import (
    Look,
    LookDetail,
    PreferenceSignal,
)
from stylecapture_backend.features.look.interfaces.http import LookHttpServices
from stylecapture_backend.features.look.ports import LookRepository
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.main import BackendServices, create_app
from stylecapture_backend.platform.session import SESSION_COOKIE_NAME, SessionSigner

SESSION_SECRET = "look-http-session-secret-with-enough-entropy"


class MemoryLooks:
    def __init__(self, look: Look) -> None:
        self.look = look
        self.signals: list[PreferenceSignal] = []

    async def list_for_user(self, user_id: UUID) -> list[Look]:
        return [self.look] if self.look.user_id == user_id else []

    async def get_detail_for_user(
        self,
        look_id: UUID,
        user_id: UUID,
    ) -> LookDetail | None:
        if self.look.id != look_id or self.look.user_id != user_id:
            return None
        return LookDetail(
            look=self.look,
            components=(),
            preference_signals=tuple(self.signals),
        )

    async def append_preference(self, signal: PreferenceSignal) -> PreferenceSignal:
        existing = next(
            (
                candidate
                for candidate in self.signals
                if candidate.idempotency_key == signal.idempotency_key
            ),
            None,
        )
        if existing is not None:
            return existing
        self.signals.append(signal)
        return signal


class MemoryLookMedia:
    def __init__(
        self,
        capture: Capture,
        look: Look,
        *,
        source_available: bool,
    ) -> None:
        self.capture = capture
        self.look = look
        self.source_available = source_available

    async def get_capture(self, capture_id: UUID) -> Capture | None:
        return self.capture if self.capture.id == capture_id else None

    def describe(self, object_key: str) -> StoredObject:
        if object_key == self.look.display_object_key:
            body = b"transparent-look"
            return StoredObject(
                owner_id=self.capture.user_id,
                object_key=object_key,
                content_type="image/png",
                byte_size=len(body),
                sha256="d" * 64,
                width=10,
                height=10,
            )
        if object_key == self.capture.source.object_key and self.source_available:
            body = b"source-frame"
            return StoredObject(
                owner_id=self.capture.user_id,
                object_key=object_key,
                content_type="image/jpeg",
                byte_size=len(body),
                sha256="s" * 64,
                width=480,
                height=854,
            )
        raise KeyError(object_key)

    def read(self, object_key: str) -> bytes:
        if object_key == self.look.display_object_key:
            return b"transparent-look"
        if object_key == self.capture.source.object_key and self.source_available:
            return b"source-frame"
        raise KeyError(object_key)


class MemoryJobs:
    def __init__(self, capture: Capture) -> None:
        self.user_id = capture.user_id
        self.job = (
            ProcessingJob.queued(capture_id=capture.id)
            .transition(JobState.PROCESSING)
            .transition(
                JobState.PARTIAL,
                error_code="vision_unavailable",
                error_message="Vision is unavailable",
            )
        )

    async def get_for_user(
        self,
        job_id: UUID,
        user_id: UUID,
    ) -> ProcessingJob | None:
        if self.job.id == job_id and self.user_id == user_id:
            return self.job
        return None

    async def get_by_capture_for_user(
        self,
        capture_id: UUID,
        user_id: UUID,
    ) -> ProcessingJob | None:
        if self.job.capture_id == capture_id and self.user_id == user_id:
            return self.job
        return None

    async def update(self, job: ProcessingJob) -> ProcessingJob:
        self.job = job
        return job


class RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID]] = []

    def enqueue_capture(self, capture_id: UUID, job_id: UUID) -> None:
        self.calls.append((capture_id, job_id))


def _capture(user_id: UUID) -> Capture:
    return Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.FEED,
            object_key="originals/feed/look.jpg",
            sha256="a" * 64,
            origin_ref="feed://outfit-1",
        ),
        ownership=OwnershipState.INSPIRATION,
        feed_context=FeedFrameContext(
            video_ref="feed://outfit-1",
            timestamp_ms=1_250,
            frame_width=480,
            frame_height=854,
            intent=FeedCaptureIntent.WHOLE_OUTFIT,
            selections=(
                FeedSelection(
                    selection_key="whole-look",
                    polygon=(
                        NormalizedPoint(0.2, 0.1),
                        NormalizedPoint(0.8, 0.1),
                        NormalizedPoint(0.8, 0.9),
                        NormalizedPoint(0.2, 0.9),
                    ),
                ),
            ),
        ),
    )


def build_client(
    *,
    display_ready: bool = True,
    source_available: bool = True,
) -> tuple[AsyncClient, Look]:
    user_id = uuid4()
    capture = _capture(user_id)
    look = Look.feed_saved(
        user_id=user_id,
        capture_id=capture.id,
        source_selection_key="whole-look",
    )
    if display_ready:
        look = replace(look, display_object_key="derived/looks/look.png")
    repository = MemoryLooks(look)
    media = MemoryLookMedia(
        capture,
        look,
        source_available=source_available,
    )
    jobs = MemoryJobs(capture)
    retries = JobRetryApplication(
        jobs=cast(JobRepository, jobs),
        dispatcher=RecordingDispatcher(),
    )
    no_op = cast(object, object())
    app = create_app(
        BackendServices(
            capture=CaptureApplication(
                captures=cast(CaptureRepository, no_op),
                objects=cast(ObjectStore, no_op),
                dispatcher=cast(JobDispatcher, no_op),
            ),
            jobs=cast(JobRepository, no_op),
            objects=cast(ObjectStore, no_op),
            retries=cast(JobRetryApplication, no_op),
            wardrobe=cast(WardrobeApplication, no_op),
            looks=LookHttpServices(
                looks=LookApplication(looks=cast(LookRepository, repository)),
                captures=media,
                jobs=cast(JobRepository, jobs),
                objects=cast(ObjectStore, media),
                retries=retries,
            ),
        ),
        session_signing_secret=SESSION_SECRET,
    )
    _, token = SessionSigner(SESSION_SECRET).issue(user_id)
    return (
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={SESSION_COOKIE_NAME: token},
        ),
        look,
    )


@pytest.mark.asyncio
async def test_owner_lists_opens_images_and_adds_optional_liking_reason() -> None:
    client, look = build_client()

    async with client:
        listed = await client.get("/v1/looks")
        detailed = await client.get(f"/v1/looks/{look.id}")
        image = await client.get(f"/v1/looks/{look.id}/image")
        source = await client.get(f"/v1/looks/{look.id}/source")
        feedback = await client.post(
            f"/v1/looks/{look.id}/feedback",
            headers={"Idempotency-Key": "reason-1"},
            json={"reason": "喜欢松弛的层次感"},
        )

    assert listed.status_code == 200
    assert listed.json()["looks"][0]["id"] == str(look.id)
    assert listed.json()["looks"][0]["display_ready"] is True
    assert listed.json()["looks"][0]["source_available"] is True
    assert detailed.status_code == 200
    assert detailed.json()["source_video_ref"] == "feed://outfit-1"
    assert detailed.json()["source_timestamp_ms"] == 1_250
    assert image.content == b"transparent-look"
    assert image.headers["content-type"] == "image/png"
    assert source.content == b"source-frame"
    assert source.headers["content-type"] == "image/jpeg"
    assert feedback.status_code == 201
    assert feedback.json()["payload"]["reason"] == "喜欢松弛的层次感"


@pytest.mark.asyncio
async def test_pending_look_does_not_use_the_full_source_frame_as_its_cover() -> None:
    client, look = build_client(display_ready=False)

    async with client:
        listed = await client.get("/v1/looks")
        image = await client.get(f"/v1/looks/{look.id}/image")
        source = await client.get(f"/v1/looks/{look.id}/source")

    summary = listed.json()["looks"][0]
    assert summary["display_ready"] is False
    assert summary["display_image_url"] is None
    assert summary["source_available"] is True
    assert image.status_code == 404
    assert source.content == b"source-frame"


@pytest.mark.asyncio
async def test_look_detail_exposes_deleted_source_state_without_a_broken_link() -> None:
    client, look = build_client(source_available=False)

    async with client:
        detail = await client.get(f"/v1/looks/{look.id}")
        source = await client.get(f"/v1/looks/{look.id}/source")

    assert detail.status_code == 200
    assert detail.json()["look"]["source_available"] is False
    assert detail.json()["look"]["source_image_url"] is None
    assert source.status_code == 404


@pytest.mark.asyncio
async def test_partial_look_can_retry_its_existing_processing_job() -> None:
    client, look = build_client()

    async with client:
        retried = await client.post(f"/v1/looks/{look.id}/retry")

    assert retried.status_code == 200
    assert retried.json()["state"] == "partial"
    assert retried.json()["attempt"] == 1


@pytest.mark.asyncio
async def test_look_routes_hide_another_users_relationship_and_images() -> None:
    client, look = build_client()
    _, token = SessionSigner(SESSION_SECRET).issue(uuid4())
    client.cookies.set(SESSION_COOKIE_NAME, token)

    async with client:
        detail = await client.get(f"/v1/looks/{look.id}")
        image = await client.get(f"/v1/looks/{look.id}/image")

    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "look_not_found"
    assert image.status_code == 404
    assert image.json()["error"]["code"] == "look_not_found"
