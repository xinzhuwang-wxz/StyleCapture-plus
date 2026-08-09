from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from pydantic import BaseModel

from stylecapture_backend.features.capture.domain import Capture
from stylecapture_backend.features.capture.ports import ObjectStore
from stylecapture_backend.features.look.application import LookApplication, LookNotFoundError
from stylecapture_backend.features.look.domain import LookDetail
from stylecapture_backend.features.render.application import RenderApplication, RenderArtifactView
from stylecapture_backend.features.render.domain import (
    RenderArtifactKind,
    RenderArtifactStatus,
    RenderPrivacy,
)
from stylecapture_backend.features.render.ports import RenderArtifactNotFound
from stylecapture_backend.features.render.signatures import (
    build_render_input_signature,
    derived_render_request_key,
)
from stylecapture_backend.platform.errors import STABLE_ERROR_RESPONSES


class CaptureReader(Protocol):
    async def get_capture(self, capture_id: UUID) -> Capture | None: ...


class RenderDispatcher(Protocol):
    def enqueue_render(self, *, user_id: UUID, artifact_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class RenderHttpServices:
    renders: RenderApplication
    looks: LookApplication
    captures: CaptureReader
    objects: ObjectStore
    dispatcher: RenderDispatcher | None = None


class RenderArtifactResponse(BaseModel):
    id: UUID
    look_id: UUID
    kind: RenderArtifactKind
    status: RenderArtifactStatus
    current: bool = True
    presentation_label: str
    subject_attached: bool
    personalized: bool
    output_image_url: str | None
    sprite_image_url: str | None = None
    sprite_status: Literal["not_applicable", "pending", "ready", "failed"] = "not_applicable"
    fallback_artifact_id: UUID | None
    failure_code: str | None
    failure_message: str | None
    retryable: bool
    share_eligible: bool
    cache_hit: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_view(
        cls,
        view: RenderArtifactView,
        *,
        current: bool = True,
    ) -> RenderArtifactResponse:
        return cls(
            id=view.id,
            look_id=view.look_id,
            kind=view.kind,
            status=view.status,
            current=current,
            presentation_label=_presentation_label(view),
            subject_attached=(
                view.kind is RenderArtifactKind.TRY_ON and view.subject_object_key is not None
            ),
            personalized=(
                view.kind is RenderArtifactKind.TRY_ON
                and view.status is RenderArtifactStatus.SUCCEEDED
                and view.subject_used
            ),
            output_image_url=(
                f"/v1/render-artifacts/{view.id}/image" if view.object_key is not None else None
            ),
            sprite_image_url=(
                f"/v1/render-artifacts/{view.id}/sprite"
                if view.sprite_object_key is not None
                else None
            ),
            sprite_status=view.sprite_status,
            fallback_artifact_id=view.fallback_artifact_id,
            failure_code=view.failure_code,
            failure_message=(
                "真实效果图暂时没有生成。可以重试。" if view.failure_code is not None else None
            ),
            retryable=view.status in {RenderArtifactStatus.FAILED, RenderArtifactStatus.DEGRADED},
            share_eligible=view.share_eligible,
            cache_hit=view.cache_hit,
            created_at=view.created_at,
            updated_at=view.updated_at,
        )


class RenderArtifactListResponse(BaseModel):
    renders: list[RenderArtifactResponse]


class CreateRenderArtifactBody(BaseModel):
    kind: RenderArtifactKind
    subject_object_key: str | None = None


def build_render_router(
    services: RenderHttpServices,
    *,
    current_user: Callable[..., UUID],
) -> APIRouter:
    router = APIRouter()
    principal = Depends(current_user)

    async def owned_detail(
        user_id: UUID,
        look_id: UUID,
    ) -> tuple[LookDetail, Capture | None]:
        detail = await services.looks.get_look(user_id=user_id, look_id=look_id)
        if detail.look.capture_id is None:
            return detail, None
        capture = await services.captures.get_capture(detail.look.capture_id)
        if capture is None or capture.user_id != user_id:
            raise LookNotFoundError("Look source not found")
        return detail, capture

    def look_display_hash(detail: LookDetail, user_id: UUID) -> str | None:
        if detail.look.display_object_key is None:
            return None
        stored = services.objects.describe(detail.look.display_object_key)
        if stored.owner_id != user_id:
            raise LookNotFoundError("Look display image not found")
        return stored.sha256

    @router.get(
        "/v1/looks/{look_id}/renders",
        response_model=RenderArtifactListResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def list_render_artifacts(
        look_id: UUID,
        user_id: UUID = principal,
    ) -> RenderArtifactListResponse:
        detail, capture = await owned_detail(user_id, look_id)
        current_collage_signature = build_render_input_signature(
            detail,
            capture,
            RenderArtifactKind.COLLAGE,
            look_display_hash=look_display_hash(detail, user_id),
        )
        views = await services.renders.list_for_look(user_id=user_id, look_id=look_id)
        for view in views:
            _dispatch_if_needed(services, view)
        return RenderArtifactListResponse(
            renders=[
                RenderArtifactResponse.from_view(
                    view,
                    current=(
                        view.kind is not RenderArtifactKind.COLLAGE
                        or view.input_hash == current_collage_signature.hash
                    ),
                )
                for view in views
            ]
        )

    @router.post(
        "/v1/looks/{look_id}/renders",
        response_model=RenderArtifactResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def create_render_artifact(
        look_id: UUID,
        body: CreateRenderArtifactBody,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        user_id: UUID = principal,
    ) -> RenderArtifactResponse:
        detail, capture = await owned_detail(user_id, look_id)
        subject_source_hash: str | None = None
        if body.subject_object_key is not None:
            if body.kind is not RenderArtifactKind.TRY_ON:
                raise ValueError("only try-on renders accept a subject photo")
            subject = services.objects.describe(body.subject_object_key)
            if subject.owner_id != user_id:
                raise LookNotFoundError("Try-on photo not found")
            subject_source_hash = subject.sha256
        base_signature = build_render_input_signature(
            detail,
            capture,
            RenderArtifactKind.COLLAGE,
            look_display_hash=look_display_hash(detail, user_id),
        )
        source_artifact: RenderArtifactView | None = None
        if body.kind is not RenderArtifactKind.COLLAGE:
            source_artifact = await services.renders.create_or_get(
                user_id=user_id,
                look_id=look_id,
                kind=RenderArtifactKind.COLLAGE,
                input_signature=base_signature,
                request_key=derived_render_request_key(
                    idempotency_key,
                    RenderArtifactKind.COLLAGE,
                ),
            )
            _dispatch_if_queued(services, source_artifact)
        view = await services.renders.create_or_get(
            user_id=user_id,
            look_id=look_id,
            kind=body.kind,
            input_signature=build_render_input_signature(
                detail,
                capture,
                body.kind,
                source_artifact=source_artifact,
                subject_source_hash=subject_source_hash,
                look_display_hash=look_display_hash(detail, user_id),
            ),
            request_key=idempotency_key,
            privacy=(
                RenderPrivacy.SHAREABLE_PIXEL
                if body.kind is RenderArtifactKind.PIXEL_COVER
                else RenderPrivacy.PRIVATE
            ),
            source_artifact_id=(source_artifact.id if source_artifact is not None else None),
            subject_object_key=body.subject_object_key,
        )
        _dispatch_if_queued(services, view)
        return RenderArtifactResponse.from_view(view)

    @router.get(
        "/v1/render-artifacts/{artifact_id}",
        response_model=RenderArtifactResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_render_artifact(
        artifact_id: UUID,
        user_id: UUID = principal,
    ) -> RenderArtifactResponse:
        return RenderArtifactResponse.from_view(
            await services.renders.get(user_id=user_id, artifact_id=artifact_id)
        )

    @router.get(
        "/v1/render-artifacts/{artifact_id}/image",
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_render_image(
        artifact_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        view = await services.renders.get(user_id=user_id, artifact_id=artifact_id)
        if view.object_key is None:
            raise RenderArtifactNotFound("Render artifact image is not ready")
        try:
            stored = services.objects.describe(view.object_key)
            body = services.objects.read(view.object_key)
        except (FileNotFoundError, KeyError) as error:
            raise RenderArtifactNotFound("Render artifact image is unavailable") from error
        return Response(
            content=body,
            media_type=stored.content_type,
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{stored.sha256}"',
            },
        )

    @router.get(
        "/v1/render-artifacts/{artifact_id}/sprite",
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_render_sprite(
        artifact_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        view = await services.renders.get(user_id=user_id, artifact_id=artifact_id)
        if view.kind is not RenderArtifactKind.PIXEL_COVER or view.sprite_object_key is None:
            raise RenderArtifactNotFound("Transparent pixel sprite is not ready")
        try:
            stored = services.objects.describe(view.sprite_object_key)
            body = services.objects.read(view.sprite_object_key)
        except (FileNotFoundError, KeyError) as error:
            raise RenderArtifactNotFound("Transparent pixel sprite is unavailable") from error
        return Response(
            content=body,
            media_type="image/png",
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{stored.sha256}"',
            },
        )

    @router.delete(
        "/v1/render-artifacts/{artifact_id}/subject",
        status_code=status.HTTP_204_NO_CONTENT,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def delete_render_subject(
        artifact_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        view = await services.renders.get(user_id=user_id, artifact_id=artifact_id)
        if view.kind is not RenderArtifactKind.TRY_ON or view.subject_object_key is None:
            raise RenderArtifactNotFound("Try-on subject photo does not exist")
        try:
            stored = services.objects.describe(view.subject_object_key)
        except (FileNotFoundError, KeyError):
            await services.renders.forget_subject_photo(
                user_id=user_id,
                artifact_id=artifact_id,
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        if stored.owner_id != user_id:
            raise RenderArtifactNotFound("Try-on subject photo does not exist")
        await services.renders.forget_subject_photo(
            user_id=user_id,
            artifact_id=artifact_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _dispatch_if_queued(
    services: RenderHttpServices,
    view: RenderArtifactView,
) -> None:
    _dispatch_if_needed(services, view)


def _dispatch_if_needed(
    services: RenderHttpServices,
    view: RenderArtifactView,
) -> None:
    if (
        services.dispatcher is not None
        and view.dispatch_required
        and (
            view.status is RenderArtifactStatus.QUEUED
            or (
                view.kind is RenderArtifactKind.PIXEL_COVER
                and view.status is RenderArtifactStatus.SUCCEEDED
                and view.sprite_status == "pending"
            )
        )
    ):
        services.dispatcher.enqueue_render(
            user_id=view.user_id,
            artifact_id=view.id,
        )


def _presentation_label(view: RenderArtifactView) -> str:
    if view.kind is RenderArtifactKind.COLLAGE:
        return "真实单品拼贴"
    if view.kind is RenderArtifactKind.TRY_ON:
        return (
            "试穿生成失败。展示真实拼贴"
            if view.status is RenderArtifactStatus.DEGRADED
            else "我的真人试穿"
            if view.subject_object_key is not None or view.subject_used
            else "固定模特预览"
        )
    return (
        "像素生成失败。展示真实拼贴"
        if view.status is RenderArtifactStatus.DEGRADED
        else "像素穿搭封面"
    )
