from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.domain import Capture, JobState, ProcessingJob
from stylecapture_backend.features.capture.infrastructure.object_store import (
    LocalObjectStore,
    StoredObject,
)
from stylecapture_backend.features.capture.ports import (
    CaptureRepository,
    CaptureSubmission,
    JobDispatcher,
    JobRepository,
    WholeOutfitRegistrar,
)
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.main import BackendServices, create_app


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (48, 64), color=(139, 92, 246)).save(buffer, format="PNG")
    return buffer.getvalue()


async def start_session(client: AsyncClient) -> UUID:
    response = await client.post("/v1/session")
    assert response.status_code == 201
    return UUID(response.json()["user_id"])


class MemoryRepository(CaptureRepository, JobRepository, WholeOutfitRegistrar):
    def __init__(self) -> None:
        self.submissions: dict[tuple[UUID, str], CaptureSubmission] = {}
        self.jobs: dict[UUID, tuple[UUID, ProcessingJob]] = {}
        self.looks: dict[UUID, PendingLookReference] = {}

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
        self.jobs[job.id] = (capture.user_id, job)
        return submission

    async def get_for_user(self, job_id: UUID, user_id: UUID) -> ProcessingJob | None:
        row = self.jobs.get(job_id)
        if row is None or row[0] != user_id:
            return None
        return row[1]

    async def get_by_capture_for_user(
        self,
        capture_id: UUID,
        user_id: UUID,
    ) -> ProcessingJob | None:
        return next(
            (
                job
                for owner_id, job in self.jobs.values()
                if owner_id == user_id and job.capture_id == capture_id
            ),
            None,
        )

    async def update(self, job: ProcessingJob) -> ProcessingJob:
        user_id, _ = self.jobs[job.id]
        self.jobs[job.id] = (user_id, job)
        return job

    async def ensure_saved_look(
        self,
        capture: Capture,
        *,
        idempotency_key: str,
    ) -> PendingLookReference:
        return self.looks.setdefault(capture.id, PendingLookReference(id=uuid4()))


@dataclass(frozen=True)
class PendingLookReference:
    id: UUID


class RecordingDispatcher(JobDispatcher):
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID]] = []

    def enqueue_capture(self, capture_id: UUID, job_id: UUID) -> None:
        self.calls.append((capture_id, job_id))


class SlowObjectStore(LocalObjectStore):
    def __init__(self, *, root: Path) -> None:
        super().__init__(
            root=root,
            signing_secret="test-http-signing-secret-with-enough-entropy",
        )
        self.heartbeat: asyncio.Event | None = None
        self.saw_heartbeat_during_parse = False
        self.active_uploads = 0
        self.max_active_uploads = 0
        self._activity_lock = threading.Lock()

    def accept_upload(
        self,
        token: str,
        *,
        body: bytes,
        content_type: str,
    ) -> StoredObject:
        with self._activity_lock:
            self.active_uploads += 1
            self.max_active_uploads = max(self.max_active_uploads, self.active_uploads)
        try:
            time.sleep(0.05)
            self.saw_heartbeat_during_parse = bool(self.heartbeat and self.heartbeat.is_set())
            return super().accept_upload(token, body=body, content_type=content_type)
        finally:
            with self._activity_lock:
                self.active_uploads -= 1


@pytest.fixture
def api(tmp_path: Path) -> tuple[AsyncClient, MemoryRepository, RecordingDispatcher]:
    repository = MemoryRepository()
    dispatcher = RecordingDispatcher()
    objects = LocalObjectStore(
        root=tmp_path / "uploads",
        signing_secret="test-http-signing-secret-with-enough-entropy",
        now=lambda: datetime(2026, 7, 25, 4, 0, tzinfo=UTC),
    )
    app = create_app(
        BackendServices(
            capture=CaptureApplication(
                captures=repository,
                objects=objects,
                dispatcher=dispatcher,
                whole_outfits=repository,
            ),
            jobs=repository,
            objects=objects,
            retries=JobRetryApplication(jobs=repository, dispatcher=dispatcher),
            wardrobe=WardrobeApplication(wardrobe=AsyncMock(), sources=objects),
        ),
        sse_poll_interval=0,
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return client, repository, dispatcher


@pytest.mark.asyncio
async def test_image_parsing_does_not_block_the_async_api_loop(tmp_path: Path) -> None:
    repository = MemoryRepository()
    dispatcher = RecordingDispatcher()
    objects = SlowObjectStore(root=tmp_path / "uploads")
    app = create_app(
        BackendServices(
            capture=CaptureApplication(
                captures=repository,
                objects=objects,
                dispatcher=dispatcher,
            ),
            jobs=repository,
            objects=objects,
            retries=JobRetryApplication(jobs=repository, dispatcher=dispatcher),
            wardrobe=WardrobeApplication(wardrobe=AsyncMock(), sources=objects),
        ),
        sse_poll_interval=0,
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    body = png_bytes()

    async with client:
        await start_session(client)
        prepared = (
            await client.post(
                "/v1/uploads/prepare",
                json={
                    "file_name": "garment.png",
                    "content_type": "image/png",
                    "byte_size": len(body),
                    "sha256": sha256(body).hexdigest(),
                },
            )
        ).json()
        objects.heartbeat = asyncio.Event()

        async def tick() -> None:
            await asyncio.sleep(0.01)
            assert objects.heartbeat is not None
            objects.heartbeat.set()

        upload, _ = await asyncio.gather(
            client.put(
                prepared["upload_url"],
                content=body,
                headers={
                    "Content-Type": "image/png",
                    "X-Upload-Token": prepared["upload_token"],
                },
            ),
            tick(),
        )

    assert upload.status_code == 201
    assert objects.saw_heartbeat_during_parse is True


@pytest.mark.asyncio
async def test_upload_processing_has_a_bounded_memory_concurrency(tmp_path: Path) -> None:
    repository = MemoryRepository()
    dispatcher = RecordingDispatcher()
    objects = SlowObjectStore(root=tmp_path / "uploads")
    app = create_app(
        BackendServices(
            capture=CaptureApplication(
                captures=repository,
                objects=objects,
                dispatcher=dispatcher,
            ),
            jobs=repository,
            objects=objects,
            retries=JobRetryApplication(jobs=repository, dispatcher=dispatcher),
            wardrobe=WardrobeApplication(wardrobe=AsyncMock(), sources=objects),
        ),
        sse_poll_interval=0,
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    body = png_bytes()

    async with client:
        await start_session(client)
        prepared_uploads = []
        for index in range(4):
            prepared = await client.post(
                "/v1/uploads/prepare",
                json={
                    "file_name": f"garment-{index}.png",
                    "content_type": "image/png",
                    "byte_size": len(body),
                    "sha256": sha256(body).hexdigest(),
                },
            )
            prepared_uploads.append(prepared.json())
        responses = await asyncio.gather(
            *(
                client.put(
                    prepared["upload_url"],
                    content=body,
                    headers={
                        "Content-Type": "image/png",
                        "X-Upload-Token": prepared["upload_token"],
                    },
                )
                for prepared in prepared_uploads
            )
        )

    assert [response.status_code for response in responses] == [201, 201, 201, 201]
    assert objects.max_active_uploads <= 2


@pytest.mark.asyncio
async def test_prepare_upload_returns_stable_error_for_unsupported_type(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    async with client:
        await start_session(client)
        response = await client.post(
            "/v1/uploads/prepare",
            json={
                "file_name": "notes.pdf",
                "content_type": "application/pdf",
                "byte_size": 32,
                "sha256": "a" * 64,
            },
        )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_image_type"
    assert response.json()["error"]["request_id"]
    assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]


@pytest.mark.asyncio
async def test_request_validation_uses_the_stable_error_envelope(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    async with client:
        await start_session(client)
        response = await client.post(
            "/v1/uploads/prepare",
            json={
                "file_name": "",
                "content_type": "image/png",
                "byte_size": 0,
                "sha256": "not-a-hash",
            },
        )

    assert response.status_code == 422
    payload = response.json()["error"]
    assert payload["code"] == "request_invalid"
    assert payload["request_id"]
    assert payload["details"]["violations"]
    assert all("input" not in violation for violation in payload["details"]["violations"])


@pytest.mark.asyncio
async def test_upload_rejects_oversized_content_length_before_image_processing(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    body = png_bytes()
    async with client:
        await start_session(client)
        prepared = (
            await client.post(
                "/v1/uploads/prepare",
                json={
                    "file_name": "garment.png",
                    "content_type": "image/png",
                    "byte_size": len(body),
                    "sha256": sha256(body).hexdigest(),
                },
            )
        ).json()
        response = await client.put(
            prepared["upload_url"],
            content=body,
            headers={
                "Content-Type": "image/png",
                "Content-Length": str(21 * 1024 * 1024),
                "X-Upload-Token": prepared["upload_token"],
            },
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_size_invalid"


@pytest.mark.asyncio
async def test_openapi_documents_generated_success_and_stable_error_contracts(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    async with client:
        schema = (await client.get("/openapi.json")).json()

    operation = schema["paths"]["/v1/uploads/prepare"]["post"]

    assert operation["responses"]["201"]["content"]["application/json"]["schema"]
    assert operation["responses"]["415"]["content"]["application/json"]["schema"]
    assert operation["responses"]["422"]["content"]["application/json"]["schema"]


@pytest.mark.asyncio
async def test_upload_and_capture_submission_are_real_and_idempotent(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, dispatcher = api
    body = png_bytes()
    async with client:
        await start_session(client)
        prepared_response = await client.post(
            "/v1/uploads/prepare",
            json={
                "file_name": "garment.png",
                "content_type": "image/png",
                "byte_size": len(body),
                "sha256": sha256(body).hexdigest(),
            },
        )
        assert prepared_response.status_code == 201
        prepared = prepared_response.json()
        assert prepared["upload_url"] == "/v1/uploads"
        assert prepared["upload_token"] not in prepared["upload_url"]

        upload_response = await client.put(
            prepared["upload_url"],
            content=body,
            headers={
                "Content-Type": "image/png",
                "X-Upload-Token": prepared["upload_token"],
            },
        )
        assert upload_response.status_code == 201

        request_body = {
            "object_key": prepared["object_key"],
            "sha256": sha256(body).hexdigest(),
            "source_kind": "camera",
            "ownership": "owned",
        }
        headers = {
            "Idempotency-Key": "mobile-capture-001",
        }
        first = await client.post("/v1/captures", json=request_body, headers=headers)
        second = await client.post("/v1/captures", json=request_body, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json() == first.json()
    assert dispatcher.calls == [
        (UUID(first.json()["capture_id"]), UUID(first.json()["job_id"])),
        (UUID(first.json()["capture_id"]), UUID(first.json()["job_id"])),
    ]
    assert first.json()["state"] == "queued"
    assert first.json()["status_url"].endswith(first.json()["job_id"])


@pytest.mark.asyncio
async def test_upload_can_only_be_discarded_before_capture_submission(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    body = png_bytes()
    digest = sha256(body).hexdigest()
    async with client:
        await start_session(client)

        unattached = (
            await client.post(
                "/v1/uploads/prepare",
                json={
                    "file_name": "discard-me.png",
                    "content_type": "image/png",
                    "byte_size": len(body),
                    "sha256": digest,
                },
            )
        ).json()
        uploaded = await client.put(
            unattached["upload_url"],
            content=body,
            headers={
                "Content-Type": "image/png",
                "X-Upload-Token": unattached["upload_token"],
            },
        )
        assert uploaded.status_code == 201
        assert (await client.delete(f"/v1/uploads/{unattached['object_key']}")).status_code == 204

        attached = (
            await client.post(
                "/v1/uploads/prepare",
                json={
                    "file_name": "keep-me.png",
                    "content_type": "image/png",
                    "byte_size": len(body),
                    "sha256": digest,
                },
            )
        ).json()
        uploaded = await client.put(
            attached["upload_url"],
            content=body,
            headers={
                "Content-Type": "image/png",
                "X-Upload-Token": attached["upload_token"],
            },
        )
        assert uploaded.status_code == 201
        submitted = await client.post(
            "/v1/captures",
            headers={"Idempotency-Key": "attached-upload-delete-guard"},
            json={
                "object_key": attached["object_key"],
                "sha256": digest,
                "source_kind": "camera",
                "ownership": "owned",
            },
        )
        assert submitted.status_code == 202

        rejected = await client.delete(f"/v1/uploads/{attached['object_key']}")

    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "upload_already_attached"


@pytest.mark.asyncio
async def test_feed_capture_accepts_and_persists_normalized_selection_paths(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, repository, _ = api
    body = png_bytes()
    async with client:
        user_id = await start_session(client)
        prepared = (
            await client.post(
                "/v1/uploads/prepare",
                json={
                    "file_name": "feed-frame.png",
                    "content_type": "image/png",
                    "byte_size": len(body),
                    "sha256": sha256(body).hexdigest(),
                },
            )
        ).json()
        upload = await client.put(
            prepared["upload_url"],
            content=body,
            headers={
                "Content-Type": "image/png",
                "X-Upload-Token": prepared["upload_token"],
            },
        )
        assert upload.status_code == 201

        response = await client.post(
            "/v1/captures",
            headers={"Idempotency-Key": "feed-http-001"},
            json={
                "object_key": prepared["object_key"],
                "sha256": sha256(body).hexdigest(),
                "source_kind": "feed",
                "ownership": "inspiration",
                "feed_context": {
                    "video_ref": "feed://demo/http-look",
                    "timestamp_ms": 1_250,
                    "frame_width": 48,
                    "frame_height": 64,
                    "selections": [
                        {
                            "selection_key": "hat",
                            "polygon": [
                                {"x": 0.1, "y": 0.1},
                                {"x": 0.4, "y": 0.1},
                                {"x": 0.3, "y": 0.3},
                            ],
                        },
                        {
                            "selection_key": "top",
                            "polygon": [
                                {"x": 0.2, "y": 0.3},
                                {"x": 0.8, "y": 0.3},
                                {"x": 0.7, "y": 0.8},
                            ],
                        },
                    ],
                },
            },
        )

    assert response.status_code == 202
    stored = repository.submissions[(user_id, "feed-http-001")].capture
    assert stored.source.origin_ref == "feed://demo/http-look"
    assert stored.feed_context is not None
    assert [selection.selection_key for selection in stored.feed_context.selections] == [
        "hat",
        "top",
    ]


@pytest.mark.asyncio
async def test_whole_outfit_capture_returns_durable_pending_look_identity(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, repository, dispatcher = api
    body = png_bytes()
    async with client:
        await start_session(client)
        prepared = (
            await client.post(
                "/v1/uploads/prepare",
                json={
                    "file_name": "whole-look.png",
                    "content_type": "image/png",
                    "byte_size": len(body),
                    "sha256": sha256(body).hexdigest(),
                },
            )
        ).json()
        await client.put(
            prepared["upload_url"],
            content=body,
            headers={
                "Content-Type": "image/png",
                "X-Upload-Token": prepared["upload_token"],
            },
        )
        response = await client.post(
            "/v1/captures",
            headers={"Idempotency-Key": "feed-http-whole-look"},
            json={
                "object_key": prepared["object_key"],
                "sha256": sha256(body).hexdigest(),
                "source_kind": "feed",
                "ownership": "inspiration",
                "feed_context": {
                    "video_ref": "feed://demo/http-whole-look",
                    "timestamp_ms": 1_250,
                    "frame_width": 48,
                    "frame_height": 64,
                    "intent": "whole_outfit",
                    "selections": [
                        {
                            "selection_key": "whole-look",
                            "polygon": [
                                {"x": 0.1, "y": 0.1},
                                {"x": 0.9, "y": 0.1},
                                {"x": 0.9, "y": 0.9},
                            ],
                        }
                    ],
                },
            },
        )

    assert response.status_code == 202
    payload = response.json()
    capture_id = UUID(payload["capture_id"])
    assert UUID(payload["look_id"]) == repository.looks[capture_id].id
    assert dispatcher.calls == [(capture_id, UUID(payload["job_id"]))]


@pytest.mark.asyncio
async def test_feed_capture_rejects_out_of_frame_points_with_stable_validation_error(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    async with client:
        await start_session(client)
        response = await client.post(
            "/v1/captures",
            headers={"Idempotency-Key": "feed-http-invalid-point"},
            json={
                "object_key": "originals/feed/invalid.webp",
                "sha256": "a" * 64,
                "source_kind": "feed",
                "ownership": "inspiration",
                "feed_context": {
                    "video_ref": "feed://demo/invalid-point",
                    "timestamp_ms": 1_250,
                    "frame_width": 48,
                    "frame_height": 64,
                    "selections": [
                        {
                            "selection_key": "hat",
                            "polygon": [
                                {"x": -0.1, "y": 0.1},
                                {"x": 0.4, "y": 0.1},
                                {"x": 0.3, "y": 0.3},
                            ],
                        }
                    ],
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request_invalid"


@pytest.mark.asyncio
async def test_feed_capture_rejects_duplicate_selection_keys_with_stable_error(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    selection = {
        "selection_key": "same-key",
        "polygon": [
            {"x": 0.1, "y": 0.1},
            {"x": 0.4, "y": 0.1},
            {"x": 0.3, "y": 0.3},
        ],
    }
    async with client:
        await start_session(client)
        response = await client.post(
            "/v1/captures",
            headers={"Idempotency-Key": "feed-http-duplicate-key"},
            json={
                "object_key": "originals/feed/duplicate.webp",
                "sha256": "a" * 64,
                "source_kind": "feed",
                "ownership": "inspiration",
                "feed_context": {
                    "video_ref": "feed://demo/duplicate-key",
                    "timestamp_ms": 1_250,
                    "frame_width": 48,
                    "frame_height": 64,
                    "selections": [selection, selection],
                },
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "feed_context_invalid"


@pytest.mark.asyncio
async def test_job_status_is_owner_scoped_and_unknown_job_uses_stable_error(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    async with client:
        await start_session(client)
        response = await client.get(f"/v1/jobs/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


@pytest.mark.asyncio
async def test_sse_emits_terminal_job_state_and_closes(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, repository, _ = api
    job = (
        ProcessingJob.queued(capture_id=uuid4())
        .transition(JobState.PROCESSING)
        .transition(JobState.READY)
    )

    async with client:
        user_id = await start_session(client)
        repository.jobs[job.id] = (user_id, job)
        response = await client.get(f"/v1/jobs/{job.id}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: job" in response.text
    assert f'"job_id":"{job.id}"' in response.text
    assert '"state":"ready"' in response.text


@pytest.mark.asyncio
async def test_failed_job_can_be_requeued_without_reuploading_the_source(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, repository, dispatcher = api
    job = (
        ProcessingJob.queued(capture_id=uuid4())
        .transition(JobState.PROCESSING)
        .transition(
            JobState.ERROR,
            error_code="vision_unavailable",
            error_message="Vision understanding is temporarily unavailable",
        )
    )

    async with client:
        user_id = await start_session(client)
        repository.jobs[job.id] = (user_id, job)
        response = await client.post(f"/v1/jobs/{job.id}/retry")

    assert response.status_code == 202
    assert response.json()["state"] == "queued"
    assert response.json()["attempt"] == 2
    assert dispatcher.calls == [(job.capture_id, job.id)]


@pytest.mark.asyncio
async def test_capture_rejects_upload_prepared_by_another_session(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    body = png_bytes()
    async with client:
        await start_session(client)
        prepared = (
            await client.post(
                "/v1/uploads/prepare",
                json={
                    "file_name": "private.png",
                    "content_type": "image/png",
                    "byte_size": len(body),
                    "sha256": sha256(body).hexdigest(),
                },
            )
        ).json()
        await client.put(
            prepared["upload_url"],
            content=body,
            headers={
                "Content-Type": "image/png",
                "X-Upload-Token": prepared["upload_token"],
            },
        )
        client.cookies.clear()
        await start_session(client)
        response = await client.post(
            "/v1/captures",
            json={
                "object_key": prepared["object_key"],
                "sha256": sha256(body).hexdigest(),
                "source_kind": "upload",
                "ownership": "owned",
            },
            headers={"Idempotency-Key": "cross-session-capture"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "upload_not_found"


@pytest.mark.asyncio
async def test_discarding_missing_private_upload_returns_stable_not_found(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    async with client:
        await start_session(client)
        response = await client.delete("/v1/uploads/users/missing/private.png")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "upload_not_found"
