from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    ImagePayload,
    NormalizedPoint,
    OwnershipState,
)
from stylecapture_backend.features.capture.infrastructure.object_store import LocalObjectStore
from stylecapture_backend.features.capture.ports import UploadRequest
from stylecapture_backend.features.look.application import LookNotFoundError
from stylecapture_backend.features.look.domain import Look, LookComponent, LookDetail
from stylecapture_backend.features.render.application import RenderApplication
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderInputSignature,
    RenderOutput,
    RenderProviderTrace,
)
from stylecapture_backend.features.render.interfaces.http import (
    RenderHttpServices,
    build_render_router,
)


class MemoryLookReader:
    def __init__(self, detail: LookDetail) -> None:
        self._detail = detail

    async def get_look(self, *, user_id: UUID, look_id: UUID) -> LookDetail:
        if self._detail.look.user_id != user_id or self._detail.look.id != look_id:
            raise LookNotFoundError("Look not found")
        return self._detail


class MemoryCaptureReader:
    def __init__(self, capture: Capture) -> None:
        self._capture = capture

    async def get_capture(self, capture_id: UUID) -> Capture | None:
        return self._capture if self._capture.id == capture_id else None


class MemoryRenderRepository:
    def __init__(self) -> None:
        self.artifacts: dict[UUID, RenderArtifact] = {}
        self.request_keys: dict[tuple[UUID, str], UUID] = {}

    async def ensure_requested(self, artifact: RenderArtifact) -> RenderArtifact:
        identity = (artifact.user_id, artifact.request_key)
        if identity in self.request_keys:
            return self.artifacts[self.request_keys[identity]]
        self.artifacts[artifact.id] = artifact
        self.request_keys[identity] = artifact.id
        return artifact

    async def save(self, artifact: RenderArtifact) -> RenderArtifact:
        self.artifacts[artifact.id] = artifact
        return artifact

    async def find_cache_hit(
        self,
        *,
        look_id: UUID,
        kind: RenderArtifactKind,
        input_signature: RenderInputSignature,
    ) -> RenderArtifact | None:
        return next(
            (
                artifact
                for artifact in self.artifacts.values()
                if artifact.look_id == look_id
                and artifact.kind is kind
                and artifact.input_signature == input_signature
                and artifact.output is not None
                and artifact.status == "succeeded"
            ),
            None,
        )

    async def list_for_look(self, *, user_id: UUID, look_id: UUID) -> list[RenderArtifact]:
        return [
            artifact
            for artifact in self.artifacts.values()
            if artifact.user_id == user_id and artifact.look_id == look_id
        ]

    async def get_for_user(self, *, user_id: UUID, artifact_id: UUID) -> RenderArtifact | None:
        artifact = self.artifacts.get(artifact_id)
        if artifact is None or artifact.user_id != user_id:
            return None
        return artifact


def png_bytes(color: tuple[int, int, int] = (139, 92, 246)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (48, 64), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def image_payload(body: bytes, object_key: str = "derived/renders/collage.png") -> ImagePayload:
    return ImagePayload(
        object_key=object_key,
        content_type="image/png",
        body=body,
        sha256=sha256(body).hexdigest(),
    )


@pytest.mark.asyncio
async def test_render_http_uses_look_artifact_contract_without_provider_leak(
    tmp_path: Path,
) -> None:
    user_id = uuid4()
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.FEED,
            object_key="originals/feed/look.png",
            sha256="a" * 64,
        ),
        ownership=OwnershipState.INSPIRATION,
    )
    look = Look.feed_saved(
        user_id=user_id,
        capture_id=capture.id,
        source_selection_key="whole1",
    )
    detail = LookDetail(
        look=look,
        components=(
            LookComponent.pending(
                look_id=look.id,
                component_key="top1",
                evidence_region=(
                    NormalizedPoint(0.1, 0.1),
                    NormalizedPoint(0.8, 0.1),
                    NormalizedPoint(0.8, 0.8),
                ),
                confidence=0.82,
                grounding_metadata={"source": "test"},
                role="上衣",
            ),
        ),
        preference_signals=(),
    )
    objects = LocalObjectStore(
        root=tmp_path / "uploads",
        signing_secret="test-render-http-signing-secret",
    )
    repository = MemoryRenderRepository()
    renders = RenderApplication(artifacts=repository)
    app = FastAPI()
    app.include_router(
        build_render_router(
            RenderHttpServices(
                renders=renders,
                looks=MemoryLookReader(detail),  # type: ignore[arg-type]
                captures=MemoryCaptureReader(capture),
                objects=objects,
            ),
            current_user=lambda: user_id,
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        requested = await client.post(
            f"/v1/looks/{look.id}/renders",
            json={"kind": "collage"},
            headers={"Idempotency-Key": "collage-1"},
        )
        listed = await client.get(f"/v1/looks/{look.id}/renders")

    assert requested.status_code == 202
    payload = requested.json()
    assert payload["kind"] == "collage"
    assert payload["status"] == "queued"
    assert payload["output_image_url"] is None
    assert payload["presentation_label"] == "真实单品拼贴"
    assert payload["personalized"] is False
    assert "provider" not in payload
    assert "model" not in payload
    assert listed.json()["renders"][0]["id"] == payload["id"]

    stored = objects.write_derived_image(
        image_payload(png_bytes()),
        owner_id=user_id,
        prefix="derived/renders",
    )
    await renders.mark_succeeded(
        user_id=user_id,
        artifact_id=UUID(payload["id"]),
        output=RenderOutput(
            object_key=stored.object_key,
            content_hash=stored.sha256,
            content_type=stored.content_type,
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed_completed = await client.get(f"/v1/looks/{look.id}/renders")
        image = await client.get(f"/v1/render-artifacts/{payload['id']}/image")

    assert listed_completed.json()["renders"][0]["output_image_url"].endswith(
        f"/{payload['id']}/image"
    )
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.content == png_bytes()


@pytest.mark.asyncio
async def test_user_can_delete_private_try_on_photo_without_deleting_result(
    tmp_path: Path,
) -> None:
    user_id = uuid4()
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.FEED,
            object_key="originals/feed/look.png",
            sha256="a" * 64,
        ),
        ownership=OwnershipState.INSPIRATION,
    )
    look = Look.feed_saved(
        user_id=user_id,
        capture_id=capture.id,
        source_selection_key="whole2",
    )
    detail = LookDetail(look=look, components=(), preference_signals=())
    objects = LocalObjectStore(
        root=tmp_path / "uploads",
        signing_secret="test-render-http-signing-secret",
    )
    subject_body = png_bytes((20, 30, 40))
    prepared = objects.prepare_upload(
        UploadRequest(
            owner_id=user_id,
            file_name="me.png",
            content_type="image/png",
            byte_size=len(subject_body),
            sha256=sha256(subject_body).hexdigest(),
        )
    )
    subject = objects.accept_upload(
        prepared.token,
        body=subject_body,
        content_type="image/png",
    )
    repository = MemoryRenderRepository()
    renders = RenderApplication(artifacts=repository)
    app = FastAPI()
    app.include_router(
        build_render_router(
            RenderHttpServices(
                renders=renders,
                looks=MemoryLookReader(detail),  # type: ignore[arg-type]
                captures=MemoryCaptureReader(capture),
                objects=objects,
            ),
            current_user=lambda: user_id,
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        requested = await client.post(
            f"/v1/looks/{look.id}/renders",
            json={"kind": "try_on", "subject_object_key": subject.object_key},
            headers={"Idempotency-Key": "try-on-private-photo"},
        )
        artifact_id = UUID(requested.json()["id"])
        await renders.mark_running(
            user_id=user_id,
            artifact_id=artifact_id,
            provider_trace=RenderProviderTrace(
                provider="litellm",
                model="image_generation",
                parameters={"personalization": "user_photo"},
            ),
        )
        result = objects.write_derived_image(
            image_payload(
                png_bytes((35, 65, 120)),
                object_key="derived/renders/personal-try-on.png",
            ),
            owner_id=user_id,
            prefix="derived/renders",
        )
        await renders.mark_succeeded(
            user_id=user_id,
            artifact_id=artifact_id,
            output=RenderOutput(
                object_key=result.object_key,
                content_hash=result.sha256,
                content_type=result.content_type,
            ),
        )
        pixel = await client.post(
            f"/v1/looks/{look.id}/renders",
            json={"kind": "pixel_cover", "source_artifact_id": str(artifact_id)},
            headers={"Idempotency-Key": "pixel-from-personal-try-on"},
        )
        deleted = await client.delete(f"/v1/render-artifacts/{requested.json()['id']}/subject")
        listed = await client.get(f"/v1/looks/{look.id}/renders")

    assert requested.status_code == 202
    assert pixel.status_code == 202
    assert repository.artifacts[UUID(pixel.json()["id"])].source_artifact_id == artifact_id
    assert pixel.json()["source_artifact_id"] == str(artifact_id)
    assert requested.json()["subject_attached"] is True
    assert requested.json()["personalized"] is False
    assert requested.json()["presentation_label"] == "我的真人试穿"
    assert deleted.status_code == 204
    assert objects.describe(subject.object_key).object_key == subject.object_key
    try_on = next(render for render in listed.json()["renders"] if render["kind"] == "try_on")
    listed_pixel = next(
        render for render in listed.json()["renders"] if render["kind"] == "pixel_cover"
    )
    assert listed_pixel["source_artifact_id"] == str(artifact_id)
    assert try_on["subject_attached"] is False
    assert try_on["personalized"] is True
    assert try_on["presentation_label"] == "我的真人试穿"
    assert try_on["output_image_url"].endswith(f"/{artifact_id}/image")
