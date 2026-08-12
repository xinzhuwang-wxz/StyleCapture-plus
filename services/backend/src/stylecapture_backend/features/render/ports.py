from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderInputSignature,
    RenderProviderTrace,
)

RENDER_TASK_NAME = "stylecapture.render.process"


class RenderIdempotencyConflict(ValueError):
    """A render request key was reused for different render semantics."""


class RenderArtifactNotFound(LookupError):
    """The requested render artifact is not visible to the current user."""


class RenderPersistenceUnavailable(RuntimeError):
    """The render artifact store is temporarily unavailable for a safe retry."""


class CollageRenderError(ValueError):
    """The Look cannot be rendered as a deterministic Item collage."""


class PixelSpriteExtractionError(ValueError):
    """A generated pixel card did not contain a safe extractable character sprite."""


class PixelSpriteExtractor(Protocol):
    def extract(self, image: ImagePayload) -> ImagePayload: ...


class RenderProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class RenderProviderUnavailable(RenderProviderError):
    def __init__(self, message: str = "Render provider is unavailable") -> None:
        super().__init__("render_provider_unavailable", message, retryable=True)


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    body: bytes
    content_type: str
    sha256: str
    provider_trace: RenderProviderTrace


class CollageRenderer(Protocol):
    def render(self, images: Sequence[ImagePayload]) -> ImagePayload: ...


class RenderArtifactRepository(Protocol):
    async def ensure_requested(self, artifact: RenderArtifact) -> RenderArtifact: ...

    async def save(self, artifact: RenderArtifact) -> RenderArtifact: ...

    async def claim_queued_for_recovery(
        self,
        *,
        user_id: UUID,
        artifact_id: UUID,
        stale_before: datetime,
    ) -> RenderArtifact | None: ...

    async def find_cache_hit(
        self,
        *,
        look_id: UUID,
        kind: RenderArtifactKind,
        input_signature: RenderInputSignature,
    ) -> RenderArtifact | None: ...

    async def list_for_look(self, *, user_id: UUID, look_id: UUID) -> list[RenderArtifact]: ...

    async def get_for_user(self, *, user_id: UUID, artifact_id: UUID) -> RenderArtifact | None: ...
