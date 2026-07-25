from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Annotated, Protocol
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
    RenderInputSignature,
    RenderPrivacy,
)
from stylecapture_backend.features.render.ports import RenderArtifactNotFound
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
    presentation_label: str
    personalized: bool
    output_image_url: str | None
    fallback_artifact_id: UUID | None
    failure_message: str | None
    retryable: bool
    share_eligible: bool
    cache_hit: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_view(cls, view: RenderArtifactView) -> RenderArtifactResponse:
        return cls(
            id=view.id,
            look_id=view.look_id,
            kind=view.kind,
            status=view.status,
            presentation_label=_presentation_label(view),
            personalized=False,
            output_image_url=(
                f"/v1/render-artifacts/{view.id}/image" if view.object_key is not None else None
            ),
            fallback_artifact_id=view.fallback_artifact_id,
            failure_message=view.failure_message,
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


def build_render_router(
    services: RenderHttpServices,
    *,
    current_user: Callable[..., UUID],
) -> APIRouter:
    router = APIRouter()
    principal = Depends(current_user)

    async def owned_detail(user_id: UUID, look_id: UUID) -> tuple[LookDetail, Capture]:
        detail = await services.looks.get_look(user_id=user_id, look_id=look_id)
        capture = await services.captures.get_capture(detail.look.capture_id)
        if capture is None or capture.user_id != user_id:
            raise LookNotFoundError("Look source not found")
        return detail, capture

    @router.get(
        "/v1/looks/{look_id}/renders",
        response_model=RenderArtifactListResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def list_render_artifacts(
        look_id: UUID,
        user_id: UUID = principal,
    ) -> RenderArtifactListResponse:
        await owned_detail(user_id, look_id)
        return RenderArtifactListResponse(
            renders=[
                RenderArtifactResponse.from_view(view)
                for view in await services.renders.list_for_look(user_id=user_id, look_id=look_id)
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
        base_signature = _input_signature(detail, capture, RenderArtifactKind.COLLAGE)
        source_artifact: RenderArtifactView | None = None
        if body.kind is not RenderArtifactKind.COLLAGE:
            source_artifact = await services.renders.create_or_get(
                user_id=user_id,
                look_id=look_id,
                kind=RenderArtifactKind.COLLAGE,
                input_signature=base_signature,
                request_key=_derived_request_key(
                    idempotency_key,
                    RenderArtifactKind.COLLAGE,
                ),
            )
            _dispatch_if_queued(services, source_artifact)
        view = await services.renders.create_or_get(
            user_id=user_id,
            look_id=look_id,
            kind=body.kind,
            input_signature=_input_signature(
                detail,
                capture,
                body.kind,
                source_artifact=source_artifact,
            ),
            request_key=idempotency_key,
            privacy=(
                RenderPrivacy.SHAREABLE_PIXEL
                if body.kind is RenderArtifactKind.PIXEL_COVER
                else RenderPrivacy.PRIVATE
            ),
            source_artifact_id=(source_artifact.id if source_artifact is not None else None),
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

    return router


def _input_signature(
    detail: LookDetail,
    capture: Capture,
    kind: RenderArtifactKind,
    *,
    source_artifact: RenderArtifactView | None = None,
) -> RenderInputSignature:
    payload = {
        "capture_source_hash": capture.source.sha256,
        "components": [
            {
                "component_key": component.component_key,
                "display_order": component.display_order,
                "item_id": str(component.item_id) if component.item_id is not None else None,
                "role": component.role,
                "status": component.status.value,
            }
            for component in detail.components
        ],
        "display_object_key": detail.look.display_object_key,
        "look_id": str(detail.look.id),
        "kind": kind.value,
        "look_status": detail.look.status.value,
        "look_updated_at": detail.look.updated_at.isoformat(),
        "source_artifact": (
            {
                "id": str(source_artifact.id),
                "input_hash": source_artifact.input_hash,
                "content_hash": source_artifact.content_hash,
            }
            if source_artifact is not None
            else None
        ),
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return RenderInputSignature(
        version="look-render-v1",
        hash=sha256(encoded.encode("utf-8")).hexdigest(),
    )


def _derived_request_key(
    request_key: str,
    kind: RenderArtifactKind,
) -> str:
    digest = sha256(request_key.encode("utf-8")).hexdigest()
    return f"auto-{kind.value}:{digest}"


def _dispatch_if_queued(
    services: RenderHttpServices,
    view: RenderArtifactView,
) -> None:
    if (
        services.dispatcher is not None
        and not view.cache_hit
        and view.status is RenderArtifactStatus.QUEUED
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
            else "固定模特效果图"
        )
    return (
        "像素生成失败。展示真实拼贴"
        if view.status is RenderArtifactStatus.DEGRADED
        else "像素穿搭封面"
    )
