from __future__ import annotations

from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import Capture
from stylecapture_backend.features.capture.ports import ObjectStore
from stylecapture_backend.features.look.application import LookApplication, LookNotFoundError
from stylecapture_backend.features.outfit.ports import OutfitPostSaveUnavailable
from stylecapture_backend.features.render.application import RenderApplication, RenderArtifactView
from stylecapture_backend.features.render.domain import (
    RenderArtifactKind,
    RenderArtifactStatus,
    RenderPrivacy,
)
from stylecapture_backend.features.render.infrastructure.tasks import RenderDispatchError
from stylecapture_backend.features.render.ports import RenderPersistenceUnavailable
from stylecapture_backend.features.render.signatures import (
    build_render_input_signature,
    derived_render_request_key,
)


class CaptureReader(Protocol):
    async def get_capture(self, capture_id: UUID) -> Capture | None: ...


class RenderDispatcher(Protocol):
    def enqueue_render(self, *, user_id: UUID, artifact_id: UUID) -> None: ...


class DefaultOutfitPresentationScheduler:
    def __init__(
        self,
        *,
        looks: LookApplication,
        captures: CaptureReader,
        objects: ObjectStore,
        renders: RenderApplication,
        dispatcher: RenderDispatcher,
    ) -> None:
        self._looks = looks
        self._captures = captures
        self._objects = objects
        self._renders = renders
        self._dispatcher = dispatcher

    async def enqueue_default_presentation(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
    ) -> None:
        try:
            await self._enqueue_default_presentation(user_id=user_id, look_id=look_id)
        except (RenderDispatchError, RenderPersistenceUnavailable) as error:
            raise OutfitPostSaveUnavailable(
                "default outfit presentation is temporarily unavailable"
            ) from error

    async def _enqueue_default_presentation(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
    ) -> None:
        detail = await self._looks.get_look(user_id=user_id, look_id=look_id)
        capture: Capture | None = None
        if detail.look.capture_id is not None:
            capture = await self._captures.get_capture(detail.look.capture_id)
            if capture is None or capture.user_id != user_id:
                raise LookNotFoundError("Look source not found")
        display_hash: str | None = None
        if detail.look.display_object_key is not None:
            stored = self._objects.describe(detail.look.display_object_key)
            if stored.owner_id != user_id:
                raise LookNotFoundError("Look display image not found")
            display_hash = stored.sha256
        request_key = f"outfit-save:{look_id}"
        collage = await self._renders.create_or_get(
            user_id=user_id,
            look_id=look_id,
            kind=RenderArtifactKind.COLLAGE,
            input_signature=build_render_input_signature(
                detail,
                capture,
                RenderArtifactKind.COLLAGE,
                look_display_hash=display_hash,
            ),
            request_key=derived_render_request_key(
                request_key,
                RenderArtifactKind.COLLAGE,
            ),
        )
        self._dispatch_if_queued(collage)
        pixel = await self._renders.create_or_get(
            user_id=user_id,
            look_id=look_id,
            kind=RenderArtifactKind.PIXEL_COVER,
            input_signature=build_render_input_signature(
                detail,
                capture,
                RenderArtifactKind.PIXEL_COVER,
                source_artifact=collage,
                look_display_hash=display_hash,
            ),
            request_key=derived_render_request_key(
                request_key,
                RenderArtifactKind.PIXEL_COVER,
            ),
            privacy=RenderPrivacy.SHAREABLE_PIXEL,
            source_artifact_id=collage.id,
        )
        self._dispatch_if_queued(pixel)

    def _dispatch_if_queued(self, view: RenderArtifactView) -> None:
        if view.dispatch_required and view.status is RenderArtifactStatus.QUEUED:
            self._dispatcher.enqueue_render(
                user_id=view.user_id,
                artifact_id=view.id,
            )
