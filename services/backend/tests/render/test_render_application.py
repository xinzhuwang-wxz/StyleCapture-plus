from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.render.application import RenderApplication
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderInputSignature,
    RenderOutput,
    RenderPrivacy,
    RenderProviderTrace,
)


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
                and artifact.status in {"succeeded", "degraded"}
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


def signature() -> RenderInputSignature:
    return RenderInputSignature(version="look-render-v1", hash="c" * 64)


def output(name: str) -> RenderOutput:
    return RenderOutput(
        object_key=f"derived/renders/{name}.webp",
        content_hash="d" * 64,
        content_type="image/webp",
    )


@pytest.mark.asyncio
async def test_create_or_get_returns_cache_hit_without_exposing_provider_trace() -> None:
    repository = MemoryRenderRepository()
    application = RenderApplication(artifacts=repository)
    user_id = uuid4()
    look_id = uuid4()

    created = await application.create_or_get(
        user_id=user_id,
        look_id=look_id,
        kind=RenderArtifactKind.COLLAGE,
        input_signature=signature(),
        request_key="collage-request",
        provider_trace=RenderProviderTrace(
            provider="deterministic-collage",
            model="collage-v1",
            parameters={"layout": "grid"},
        ),
    )
    succeeded = await application.mark_succeeded(
        user_id=user_id,
        artifact_id=created.id,
        output=output("collage"),
    )
    cached = await application.create_or_get(
        user_id=user_id,
        look_id=look_id,
        kind=RenderArtifactKind.COLLAGE,
        input_signature=signature(),
        request_key="collage-request-2",
    )

    assert succeeded.object_key == "derived/renders/collage.webp"
    assert cached.id == succeeded.id
    assert cached.cache_hit is True
    assert not hasattr(cached, "provider_trace")


@pytest.mark.asyncio
async def test_degraded_try_on_view_keeps_fallback_relationship_and_not_shareable() -> None:
    repository = MemoryRenderRepository()
    application = RenderApplication(artifacts=repository)
    user_id = uuid4()
    look_id = uuid4()
    collage = await application.create_or_get(
        user_id=user_id,
        look_id=look_id,
        kind=RenderArtifactKind.COLLAGE,
        input_signature=signature(),
        request_key="collage-request",
    )
    await application.mark_succeeded(
        user_id=user_id,
        artifact_id=collage.id,
        output=output("collage"),
    )
    try_on = await application.create_or_get(
        user_id=user_id,
        look_id=look_id,
        kind=RenderArtifactKind.TRY_ON,
        input_signature=signature(),
        request_key="try-on-request",
    )

    degraded = await application.degrade_to_fallback(
        user_id=user_id,
        artifact_id=try_on.id,
        fallback_artifact_id=collage.id,
        reason="category unsupported; showing collage",
    )

    assert degraded.status == "degraded"
    assert degraded.fallback_artifact_id == collage.id
    assert degraded.share_eligible is False


@pytest.mark.asyncio
async def test_only_pixel_cover_views_report_share_eligibility() -> None:
    repository = MemoryRenderRepository()
    application = RenderApplication(artifacts=repository)
    pixel = await application.create_or_get(
        user_id=uuid4(),
        look_id=uuid4(),
        kind=RenderArtifactKind.PIXEL_COVER,
        input_signature=signature(),
        request_key="pixel-request",
        privacy=RenderPrivacy.SHAREABLE_PIXEL,
    )

    succeeded = await application.mark_succeeded(
        user_id=pixel.user_id,
        artifact_id=pixel.id,
        output=output("pixel"),
    )

    assert succeeded.share_eligible is True
