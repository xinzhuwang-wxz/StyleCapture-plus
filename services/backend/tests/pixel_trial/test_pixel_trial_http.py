from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from io import BytesIO
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.infrastructure.object_store import LocalObjectStore
from stylecapture_backend.features.capture.ports import (
    JobRepository,
    UploadRequest,
)
from stylecapture_backend.features.pixel_trial.application import PixelTrialApplication
from stylecapture_backend.features.pixel_trial.domain import PixelTrial
from stylecapture_backend.features.pixel_trial.interfaces.http import PixelTrialHttpServices
from stylecapture_backend.features.pixel_trial.ports import PixelTrialIdempotencyConflict
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.main import BackendServices, create_app


def png_bytes(color: tuple[int, int, int] = (139, 92, 246)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 96), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


class MemoryPixelTrials:
    def __init__(self) -> None:
        self.trials: dict[UUID, PixelTrial] = {}
        self.by_request: dict[tuple[UUID, str], UUID] = {}

    async def ensure_requested(self, trial: PixelTrial) -> PixelTrial:
        key = (trial.user_id, trial.request_key)
        existing_id = self.by_request.get(key)
        if existing_id is not None:
            existing = self.trials[existing_id]
            if existing.subject_object_key != trial.subject_object_key:
                raise PixelTrialIdempotencyConflict(
                    "Pixel trial idempotency key was reused with a different subject"
                )
            return existing
        self.trials[trial.id] = trial
        self.by_request[key] = trial.id
        return trial

    async def save(self, trial: PixelTrial) -> PixelTrial:
        self.trials[trial.id] = trial
        self.by_request[(trial.user_id, trial.request_key)] = trial.id
        return trial

    async def get_for_user(
        self,
        *,
        user_id: UUID,
        trial_id: UUID,
    ) -> PixelTrial | None:
        trial = self.trials.get(trial_id)
        return trial if trial is not None and trial.user_id == user_id else None

    async def delete_for_user(
        self,
        *,
        user_id: UUID,
        trial_id: UUID,
    ) -> PixelTrial | None:
        trial = await self.get_for_user(user_id=user_id, trial_id=trial_id)
        if trial is None:
            return None
        self.trials.pop(trial_id, None)
        self.by_request.pop((user_id, trial.request_key), None)
        return trial


class RecordingPixelTrialDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID]] = []

    def enqueue_pixel_trial(self, *, user_id: UUID, trial_id: UUID) -> None:
        self.calls.append((user_id, trial_id))


async def start_session(client: AsyncClient) -> UUID:
    response = await client.post("/v1/session")
    assert response.status_code == 201
    return UUID(response.json()["user_id"])


def store_private_image(
    objects: LocalObjectStore,
    *,
    user_id: UUID,
    body: bytes,
) -> str:
    digest = sha256(body).hexdigest()
    prepared = objects.prepare_upload(
        UploadRequest(
            owner_id=user_id,
            file_name="full-body.png",
            content_type="image/png",
            byte_size=len(body),
            sha256=digest,
        ),
        ttl=timedelta(minutes=5),
    )
    return objects.accept_upload(
        prepared.token,
        body=body,
        content_type="image/png",
    ).object_key


@pytest.mark.asyncio
async def test_pixel_trial_http_creates_private_queued_task(tmp_path) -> None:
    repository = MemoryPixelTrials()
    dispatcher = RecordingPixelTrialDispatcher()
    objects = LocalObjectStore(
        root=tmp_path / "uploads",
        signing_secret="test-http-signing-secret-with-enough-entropy",
    )
    app = create_app(
        BackendServices(
            capture=cast(CaptureApplication, None),
            jobs=cast(JobRepository, None),
            objects=objects,
            retries=cast(JobRetryApplication, None),
            wardrobe=WardrobeApplication(wardrobe=cast(object, None), sources=objects),
            pixel_trials=PixelTrialHttpServices(
                trials=PixelTrialApplication(trials=repository),
                objects=objects,
                dispatcher=dispatcher,
            ),
        ),
        sse_poll_interval=0,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        user_id = await start_session(client)
        object_key = store_private_image(objects, user_id=user_id, body=png_bytes())
        created = await client.post(
            "/v1/pixel-trials",
            headers={"Idempotency-Key": "pixel-try-1"},
            json={"subject_object_key": object_key},
        )
        assert created.status_code == 202
        payload = created.json()
        assert payload["status"] == "queued"
        assert payload["subject_attached"] is True
        assert payload["output_image_url"] is None
        assert "provider" not in payload
        assert "model" not in payload
        assert dispatcher.calls == [(user_id, UUID(payload["id"]))]

        not_ready = await client.get(f"/v1/pixel-trials/{payload['id']}/image")
        assert not_ready.status_code == 404
        assert not_ready.json()["error"]["code"] == "pixel_trial_not_found"


@pytest.mark.asyncio
async def test_pixel_trial_rejects_other_users_subject_photo(tmp_path) -> None:
    repository = MemoryPixelTrials()
    objects = LocalObjectStore(
        root=tmp_path / "uploads",
        signing_secret="test-http-signing-secret-with-enough-entropy",
    )
    app = create_app(
        BackendServices(
            capture=cast(CaptureApplication, None),
            jobs=cast(JobRepository, None),
            objects=objects,
            retries=cast(JobRetryApplication, None),
            wardrobe=WardrobeApplication(wardrobe=cast(object, None), sources=objects),
            pixel_trials=PixelTrialHttpServices(
                trials=PixelTrialApplication(trials=repository),
                objects=objects,
            ),
        ),
        sse_poll_interval=0,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await start_session(client)
        owner_id = uuid4()
        object_key = store_private_image(objects, user_id=owner_id, body=png_bytes())

        response = await client.post(
            "/v1/pixel-trials",
            headers={"Idempotency-Key": "pixel-try-other-user"},
            json={"subject_object_key": object_key},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "pixel_trial_not_found"
