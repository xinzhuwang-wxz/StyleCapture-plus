from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from pydantic import BaseModel, Field

from stylecapture_backend.features.capture.application import JobRetryApplication
from stylecapture_backend.features.capture.domain import Capture, JobState
from stylecapture_backend.features.capture.ports import JobRepository, ObjectStore
from stylecapture_backend.features.item_presentation.application import (
    ItemPresentationApplication,
    ItemPresentationView,
)
from stylecapture_backend.features.item_presentation.domain import ItemPresentationStatus
from stylecapture_backend.features.look.application import LookApplication, LookNotFoundError
from stylecapture_backend.features.look.domain import (
    Look,
    LookAnalysis,
    LookComponent,
    LookDetail,
    LookSource,
    LookStatus,
    PreferenceSignal,
    PreferenceSignalKind,
)
from stylecapture_backend.platform.errors import STABLE_ERROR_RESPONSES


class CaptureReader(Protocol):
    async def get_capture(self, capture_id: UUID) -> Capture | None: ...


@dataclass(frozen=True, slots=True)
class LookHttpServices:
    looks: LookApplication
    captures: CaptureReader
    jobs: JobRepository
    objects: ObjectStore
    retries: JobRetryApplication
    item_presentations: ItemPresentationApplication | None = None


class LookImageNotFoundError(FileNotFoundError):
    """The Look's derived or source image is unavailable."""


class LookSummaryResponse(BaseModel):
    id: UUID
    capture_id: UUID | None
    status: LookStatus
    source: LookSource
    display_name: str
    display_image_url: str | None
    source_image_url: str | None
    display_ready: bool
    source_available: bool
    fixed_presentation: bool = False
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        look: Look,
        *,
        source_available: bool,
    ) -> LookSummaryResponse:
        return cls(
            id=look.id,
            capture_id=look.capture_id,
            status=look.status,
            source=look.source,
            display_name=(
                look.analysis.display_name if look.analysis is not None else "穿搭整理中"
            ),
            display_image_url=(
                f"/v1/looks/{look.id}/image" if look.display_object_key is not None else None
            ),
            source_image_url=(f"/v1/looks/{look.id}/source" if source_available else None),
            display_ready=look.display_object_key is not None,
            source_available=source_available,
            fixed_presentation=(
                look.source_selection_key.startswith("seed_")
                and look.display_object_key is not None
            ),
            created_at=look.created_at,
            updated_at=look.updated_at,
        )


class LookListResponse(BaseModel):
    looks: list[LookSummaryResponse]


class LookComponentResponse(BaseModel):
    component_key: str
    status: str
    item_id: UUID | None
    item_image_url: str | None
    item_image_status: ItemPresentationStatus | None = None
    role: str | None
    layer: str | None
    display_order: int
    confidence: float

    @classmethod
    def from_domain(
        cls,
        component: LookComponent,
        *,
        flat_lay: ItemPresentationView | None = None,
    ) -> LookComponentResponse:
        flat_lay_image_url = (
            f"/v1/item-presentations/{flat_lay.id}/image"
            if (
                flat_lay is not None
                and flat_lay.status is ItemPresentationStatus.SUCCEEDED
                and flat_lay.object_key is not None
            )
            else None
        )
        return cls(
            component_key=component.component_key,
            status=component.status.value,
            item_id=component.item_id,
            item_image_url=(
                flat_lay_image_url
                or (
                    f"/v1/items/{component.item_id}/image"
                    if component.item_id is not None
                    else None
                )
            ),
            item_image_status=flat_lay.status if flat_lay is not None else None,
            role=component.role,
            layer=component.layer,
            display_order=component.display_order,
            confidence=component.confidence,
        )


class LookAnalysisResponse(BaseModel):
    values: dict[str, str]
    confidence: dict[str, float]
    capability_alias: str
    model_version: str
    prompt_version: str
    schema_version: str
    taxonomy_version: str

    @classmethod
    def from_domain(cls, analysis: LookAnalysis) -> LookAnalysisResponse:
        fields = {
            "color": analysis.color,
            "silhouette": analysis.silhouette,
            "material": analysis.material,
            "layering": analysis.layering,
            "focal_point": analysis.focal_point,
            "scene": analysis.scene,
            "style": analysis.style,
        }
        if analysis.title is not None:
            fields["title"] = analysis.title
        return cls(
            values={name: field.value for name, field in fields.items()},
            confidence={name: field.confidence for name, field in fields.items()},
            capability_alias=analysis.metadata.capability_alias,
            model_version=analysis.metadata.model_version,
            prompt_version=analysis.metadata.prompt_version,
            schema_version=analysis.metadata.schema_version,
            taxonomy_version=analysis.metadata.taxonomy_version,
        )


class PreferenceResponse(BaseModel):
    id: UUID
    kind: PreferenceSignalKind
    payload: dict[str, object]
    created_at: datetime

    @classmethod
    def from_domain(cls, signal: PreferenceSignal) -> PreferenceResponse:
        return cls(
            id=signal.id,
            kind=signal.kind,
            payload=dict(signal.payload),
            created_at=signal.created_at,
        )


class LookDetailResponse(BaseModel):
    look: LookSummaryResponse
    components: list[LookComponentResponse]
    analysis: LookAnalysisResponse | None
    preferences: list[PreferenceResponse]
    source_video_ref: str | None
    source_timestamp_ms: int | None

    @classmethod
    def from_domain(
        cls,
        detail: LookDetail,
        capture: Capture | None,
        *,
        source_available: bool,
        flat_lays: Mapping[UUID, ItemPresentationView] | None = None,
    ) -> LookDetailResponse:
        context = capture.feed_context if capture is not None else None
        return cls(
            look=LookSummaryResponse.from_domain(
                detail.look,
                source_available=source_available,
            ),
            components=[
                LookComponentResponse.from_domain(
                    component,
                    flat_lay=(
                        (flat_lays or {}).get(component.item_id)
                        if component.item_id is not None
                        else None
                    ),
                )
                for component in detail.components
            ],
            analysis=(
                LookAnalysisResponse.from_domain(detail.look.analysis)
                if detail.look.analysis is not None
                else None
            ),
            preferences=[
                PreferenceResponse.from_domain(signal) for signal in detail.preference_signals
            ],
            source_video_ref=context.video_ref if context is not None else None,
            source_timestamp_ms=context.timestamp_ms if context is not None else None,
        )


class AddLikingReasonBody(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class LookRetryResponse(BaseModel):
    job_id: UUID
    state: JobState
    attempt: int


class LookDeletionResponse(BaseModel):
    look_id: UUID
    deleted_item_ids: list[UUID]
    preserved_shared_item_ids: list[UUID]


def build_look_router(
    services: LookHttpServices,
    *,
    current_user: Callable[..., UUID],
) -> APIRouter:
    router = APIRouter(prefix="/v1/looks")
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

    def source_available(look: Look, capture: Capture | None) -> bool:
        if look.source is LookSource.AI_GENERATED or capture is None:
            return False
        try:
            services.objects.describe(capture.source.object_key)
        except (FileNotFoundError, KeyError):
            return False
        return True

    async def summary(look: Look) -> LookSummaryResponse:
        capture = (
            await services.captures.get_capture(look.capture_id)
            if look.capture_id is not None
            else None
        )
        available = (
            capture is not None
            and capture.user_id == look.user_id
            and source_available(look, capture)
        )
        return LookSummaryResponse.from_domain(
            look,
            source_available=available,
        )

    async def image_response(
        user_id: UUID,
        look_id: UUID,
        *,
        source_only: bool,
    ) -> Response:
        detail, capture = await owned_detail(user_id, look_id)
        if source_only and capture is None:
            raise LookImageNotFoundError(look_id)
        object_key = (
            capture.source.object_key
            if source_only and capture is not None
            else detail.look.display_object_key
        )
        if object_key is None:
            raise LookImageNotFoundError(look_id)
        try:
            stored = services.objects.describe(object_key)
            body = services.objects.read(object_key)
        except (FileNotFoundError, KeyError) as error:
            raise LookImageNotFoundError(look_id) from error
        return Response(
            content=body,
            media_type=stored.content_type,
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{stored.sha256}"',
            },
        )

    @router.get("", response_model=LookListResponse, responses=STABLE_ERROR_RESPONSES)
    async def list_looks(user_id: UUID = principal) -> LookListResponse:
        looks = await services.looks.list_looks(user_id=user_id)
        return LookListResponse(looks=[await summary(look) for look in looks])

    @router.get(
        "/{look_id}",
        response_model=LookDetailResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_look(
        look_id: UUID,
        user_id: UUID = principal,
    ) -> LookDetailResponse:
        detail, capture = await owned_detail(user_id, look_id)
        flat_lays: dict[UUID, ItemPresentationView] = {}
        if services.item_presentations is not None:
            item_ids = {
                component.item_id
                for component in detail.components
                if component.item_id is not None
            }
            for item_id in item_ids:
                presentation = await services.item_presentations.get_current_flat_lay_item(
                    user_id=user_id,
                    item_id=item_id,
                )
                if presentation is not None:
                    flat_lays[item_id] = presentation
        return LookDetailResponse.from_domain(
            detail,
            capture,
            source_available=source_available(detail.look, capture),
            flat_lays=flat_lays,
        )

    @router.delete(
        "/{look_id}",
        response_model=LookDeletionResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def delete_look(
        look_id: UUID,
        delete_items: bool = False,
        user_id: UUID = principal,
    ) -> LookDeletionResponse:
        result = await services.looks.delete_look(
            user_id=user_id,
            look_id=look_id,
            delete_items=delete_items,
        )
        return LookDeletionResponse(
            look_id=result.look_id,
            deleted_item_ids=list(result.deleted_item_ids),
            preserved_shared_item_ids=list(result.preserved_shared_item_ids),
        )

    @router.get("/{look_id}/image", responses=STABLE_ERROR_RESPONSES)
    async def get_look_image(
        look_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        return await image_response(user_id, look_id, source_only=False)

    @router.get("/{look_id}/source", responses=STABLE_ERROR_RESPONSES)
    async def get_look_source(
        look_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        return await image_response(user_id, look_id, source_only=True)

    @router.post(
        "/{look_id}/retry",
        response_model=LookRetryResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def retry_look(
        look_id: UUID,
        user_id: UUID = principal,
    ) -> LookRetryResponse:
        _, capture = await owned_detail(user_id, look_id)
        if capture is None:
            raise LookNotFoundError("AI-generated Look has no capture job to retry")
        job = await services.jobs.get_by_capture_for_user(capture.id, user_id)
        if job is None:
            raise LookNotFoundError("Look processing job not found")
        retried = await services.retries.retry(user_id, job.id)
        return LookRetryResponse(
            job_id=retried.id,
            state=retried.state,
            attempt=retried.attempt,
        )

    @router.post(
        "/{look_id}/feedback",
        response_model=PreferenceResponse,
        status_code=status.HTTP_201_CREATED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def add_liking_reason(
        look_id: UUID,
        body: AddLikingReasonBody,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        user_id: UUID = principal,
    ) -> PreferenceResponse:
        signal = await services.looks.record_liking_reason(
            user_id=user_id,
            look_id=look_id,
            reason=body.reason,
            idempotency_key=idempotency_key,
        )
        return PreferenceResponse.from_domain(signal)

    return router
