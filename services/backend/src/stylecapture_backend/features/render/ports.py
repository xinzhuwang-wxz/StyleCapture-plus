from __future__ import annotations

from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderInputSignature,
)


class RenderIdempotencyConflict(ValueError):
    """A render request key was reused for different render semantics."""


class RenderArtifactNotFound(LookupError):
    """The requested render artifact is not visible to the current user."""


class RenderPersistenceUnavailable(RuntimeError):
    """The render artifact store is temporarily unavailable for a safe retry."""


class RenderArtifactRepository(Protocol):
    async def ensure_requested(self, artifact: RenderArtifact) -> RenderArtifact: ...

    async def save(self, artifact: RenderArtifact) -> RenderArtifact: ...

    async def find_cache_hit(
        self,
        *,
        look_id: UUID,
        kind: RenderArtifactKind,
        input_signature: RenderInputSignature,
    ) -> RenderArtifact | None: ...

    async def list_for_look(self, *, user_id: UUID, look_id: UUID) -> list[RenderArtifact]: ...

    async def get_for_user(self, *, user_id: UUID, artifact_id: UUID) -> RenderArtifact | None: ...
