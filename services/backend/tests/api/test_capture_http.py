from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from stylecapture_backend.features.capture.application import CaptureApplication
from stylecapture_backend.features.capture.domain import Capture, JobState, ProcessingJob
from stylecapture_backend.features.capture.infrastructure.object_store import LocalObjectStore
from stylecapture_backend.features.capture.ports import (
    CaptureRepository,
    CaptureSubmission,
    JobDispatcher,
    JobRepository,
)
from stylecapture_backend.main import BackendServices, create_app


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (48, 64), color=(139, 92, 246)).save(buffer, format="PNG")
    return buffer.getvalue()


class MemoryRepository(CaptureRepository, JobRepository):
    def __init__(self) -> None:
        self.submissions: dict[tuple[UUID, str], CaptureSubmission] = {}
        self.jobs: dict[UUID, tuple[UUID, ProcessingJob]] = {}

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

    async def update(self, job: ProcessingJob) -> ProcessingJob:
        user_id, _ = self.jobs[job.id]
        self.jobs[job.id] = (user_id, job)
        return job


class RecordingDispatcher(JobDispatcher):
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID]] = []

    def enqueue_capture(self, capture_id: UUID, job_id: UUID) -> None:
        self.calls.append((capture_id, job_id))


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
            ),
            jobs=repository,
            objects=objects,
        ),
        sse_poll_interval=0,
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return client, repository, dispatcher


@pytest.mark.asyncio
async def test_prepare_upload_returns_stable_error_for_unsupported_type(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    async with client:
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


@pytest.mark.asyncio
async def test_upload_rejects_oversized_content_length_before_image_processing(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    body = png_bytes()
    async with client:
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
    user_id = uuid4()
    body = png_bytes()
    async with client:
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

        upload_response = await client.put(
            prepared["upload_url"],
            content=body,
            headers={"Content-Type": "image/png"},
        )
        assert upload_response.status_code == 201

        request_body = {
            "object_key": prepared["object_key"],
            "sha256": sha256(body).hexdigest(),
            "source_kind": "camera",
            "ownership": "owned",
        }
        headers = {
            "X-StyleCapture-User": str(user_id),
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
async def test_job_status_is_owner_scoped_and_unknown_job_uses_stable_error(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, _, _ = api
    async with client:
        response = await client.get(
            f"/v1/jobs/{uuid4()}",
            headers={"X-StyleCapture-User": str(uuid4())},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


@pytest.mark.asyncio
async def test_sse_emits_terminal_job_state_and_closes(
    api: tuple[AsyncClient, MemoryRepository, RecordingDispatcher],
) -> None:
    client, repository, _ = api
    user_id = uuid4()
    job = (
        ProcessingJob.queued(capture_id=uuid4())
        .transition(JobState.PROCESSING)
        .transition(JobState.READY)
    )
    repository.jobs[job.id] = (user_id, job)

    async with client:
        response = await client.get(
            f"/v1/jobs/{job.id}/events",
            headers={"X-StyleCapture-User": str(user_id)},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: job" in response.text
    assert f'"job_id":"{job.id}"' in response.text
    assert '"state":"ready"' in response.text
