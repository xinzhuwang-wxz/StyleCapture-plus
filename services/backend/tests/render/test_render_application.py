from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.render.application import RenderApplication
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderInputSignature,
)


class QueuedRepository:
    def __init__(self) -> None:
        self.artifact: RenderArtifact | None = None

    async def ensure_requested(self, artifact: RenderArtifact) -> RenderArtifact:
        if self.artifact is None:
            self.artifact = artifact
        return self.artifact

    async def save(self, artifact: RenderArtifact) -> RenderArtifact:
        self.artifact = artifact
        return artifact

    async def find_cache_hit(
        self,
        *,
        look_id: UUID,
        kind: RenderArtifactKind,
        input_signature: RenderInputSignature,
    ) -> RenderArtifact | None:
        return None

    async def list_for_look(self, *, user_id: UUID, look_id: UUID) -> list[RenderArtifact]:
        return [self.artifact] if self.artifact is not None else []

    async def get_for_user(
        self,
        *,
        user_id: UUID,
        artifact_id: UUID,
    ) -> RenderArtifact | None:
        return self.artifact


@pytest.mark.asyncio
async def test_existing_queued_artifact_is_redispatched_after_broker_failure() -> None:
    repository = QueuedRepository()
    application = RenderApplication(artifacts=repository)
    user_id = uuid4()
    look_id = uuid4()
    kind = RenderArtifactKind.COLLAGE
    input_signature = RenderInputSignature(version="render-v1", hash="a" * 64)

    first = await application.create_or_get(
        user_id=user_id,
        look_id=look_id,
        kind=kind,
        input_signature=input_signature,
        request_key="retryable-render",
    )
    retried = await application.create_or_get(
        user_id=user_id,
        look_id=look_id,
        kind=kind,
        input_signature=input_signature,
        request_key="retryable-render",
    )

    assert first.id == retried.id
    assert first.dispatch_required is True
    assert retried.dispatch_required is True
