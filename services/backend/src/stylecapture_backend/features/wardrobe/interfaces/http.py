from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field, model_validator
from stylecapture_backend.features.capture.domain import (
    CaptureSourceKind,
    JobState,
    OwnershipState,
)
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationStatus,
)
from stylecapture_backend.features.item_presentation.interfaces.http import (
    ItemPresentationHttpServices,
)
from stylecapture_backend.features.item_presentation.ports import (
    ItemPresentationDispatchError,
)
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.features.wardrobe.domain import (
    FieldEnvelope,
    FieldProvenance,
    ItemStatus,
    WardrobeItem,
)
from stylecapture_backend.platform.errors import STABLE_ERROR_RESPONSES

DisplayImageKind = Literal["derived_garment", "source_capture"]
DisplayImageIssue = Literal[
    "multiple_garments",
    "no_reliable_garment",
    "normalization_unavailable",
]


class FieldResponse(BaseModel):
    value: object
    provenance: FieldProvenance
    confidence: float
    model_version: str | None
    locked: bool

    @classmethod
    def from_domain(cls, field: FieldEnvelope) -> FieldResponse:
        return cls(
            value=field.value,
            provenance=field.provenance,
            confidence=field.confidence,
            model_version=field.model_version,
            locked=field.locked,
        )


class ItemResponse(BaseModel):
    id: UUID
    capture_id: UUID
    status: ItemStatus
    ownership: OwnershipState
    source_kind: CaptureSourceKind
    source_video_ref: str | None = None
    source_timestamp_ms: int | None = None
    display_image_url: str
    display_image_kind: DisplayImageKind = "source_capture"
    display_image_issue: DisplayImageIssue | None = None
    pixel_image_url: str | None = None
    pixel_image_status: ItemPresentationStatus | None = None
    source_image_url: str
    source_available: bool
    attributes: dict[str, FieldResponse]
    model_metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        item: WardrobeItem,
        *,
        pixel_image_url: str | None = None,
        pixel_image_status: ItemPresentationStatus | None = None,
    ) -> ItemResponse:
        normalization = item.model_metadata.get("normalization")
        display_image_issue: DisplayImageIssue | None = None
        if item.display_object_key is None and isinstance(normalization, Mapping):
            reason = normalization.get("reason")
            if reason == "multiple_garments":
                display_image_issue = "multiple_garments"
            elif reason == "no_reliable_garment":
                display_image_issue = "no_reliable_garment"
            elif normalization.get("status") == "fallback":
                display_image_issue = "normalization_unavailable"
        feed_source = item.model_metadata.get("feed_source")
        source_video_ref = None
        source_timestamp_ms = None
        if isinstance(feed_source, Mapping):
            raw_video_ref = feed_source.get("video_ref")
            raw_timestamp_ms = feed_source.get("timestamp_ms")
            if isinstance(raw_video_ref, str) and raw_video_ref:
                source_video_ref = raw_video_ref
            if isinstance(raw_timestamp_ms, int) and raw_timestamp_ms >= 0:
                source_timestamp_ms = raw_timestamp_ms
        return cls(
            id=item.id,
            capture_id=item.capture_id,
            status=item.status,
            ownership=item.ownership,
            source_kind=item.source_kind,
            source_video_ref=source_video_ref,
            source_timestamp_ms=source_timestamp_ms,
            display_image_url=f"/v1/items/{item.id}/image",
            display_image_kind=(
                "derived_garment"
                if item.display_object_key is not None
                else "source_capture"
            ),
            display_image_issue=display_image_issue,
            pixel_image_url=pixel_image_url,
            pixel_image_status=pixel_image_status,
            source_image_url=f"/v1/items/{item.id}/source",
            source_available=item.source_available,
            attributes={
                name: FieldResponse.from_domain(field)
                for name, field in item.attributes.fields.items()
            },
            model_metadata={
                name: item.model_metadata[name]
                for name in (
                    "capability_alias",
                    "prompt_version",
                    "schema_version",
                    "taxonomy_version",
                    "latency_ms",
                )
                if name in item.model_metadata
            },
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class ItemListResponse(BaseModel):
    items: list[ItemResponse]


class ItemRetryResponse(BaseModel):
    job_id: UUID
    state: JobState
    attempt: int


CorrectionValue = str | list[str]


class UpdateItemBody(BaseModel):
    ownership: OwnershipState | None = None
    corrections: dict[str, CorrectionValue] = Field(default_factory=dict, max_length=15)

    @model_validator(mode="after")
    def validate_update(self) -> UpdateItemBody:
        if self.ownership is None and not self.corrections:
            raise ValueError("At least one ownership or correction value is required")
        for name, value in self.corrections.items():
            if not name.strip() or len(name) > 80:
                raise ValueError("Correction field names must contain 1 to 80 characters")
            values = value if isinstance(value, list) else [value]
            if len(values) > 12 or any(not entry.strip() or len(entry) > 1000 for entry in values):
                raise ValueError("Correction values exceed the supported size")
        return self


class ItemSourceNotFoundError(FileNotFoundError):
    pass


def build_wardrobe_router(
    application: WardrobeApplication,
    *,
    current_user: Callable[..., UUID],
    presentations: ItemPresentationHttpServices | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/v1/items")
    principal = Depends(current_user)

    async def response_for(item: WardrobeItem, user_id: UUID) -> ItemResponse:
        if presentations is None or item.status not in {ItemStatus.READY, ItemStatus.PARTIAL}:
            return ItemResponse.from_domain(item)
        presentation = await presentations.presentations.ensure_pixel_item(
            user_id=user_id,
            item_id=item.id,
        )
        if (
            presentations.dispatcher is not None
            and presentation.dispatch_required
            and presentation.status is ItemPresentationStatus.QUEUED
        ):
            try:
                presentations.dispatcher.enqueue_item_presentation(
                    user_id=presentation.user_id,
                    asset_id=presentation.id,
                )
            except ItemPresentationDispatchError:
                presentation = await presentations.presentations.mark_failed(
                    user_id=presentation.user_id,
                    asset_id=presentation.id,
                    code="dispatch_unavailable",
                    message="像素展示图会稍后再生成, 真实单品已经可以正常使用",
                )
        return ItemResponse.from_domain(
            item,
            pixel_image_url=(
                f"/v1/item-presentations/{presentation.id}/image"
                if presentation.object_key is not None
                else None
            ),
            pixel_image_status=presentation.status,
        )

    @router.get(
        "",
        response_model=ItemListResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def list_items(
        user_id: UUID = principal,
    ) -> ItemListResponse:
        items = await application.list_items(user_id)
        return ItemListResponse(items=[await response_for(item, user_id) for item in items])

    @router.get(
        "/{item_id}",
        response_model=ItemResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_item(
        item_id: UUID,
        user_id: UUID = principal,
    ) -> ItemResponse:
        return await response_for(
            await application.get_item(user_id, item_id),
            user_id,
        )

    @router.patch(
        "/{item_id}",
        response_model=ItemResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def update_item(
        item_id: UUID,
        body: UpdateItemBody,
        user_id: UUID = principal,
    ) -> ItemResponse:
        item = await application.update_item(
            user_id,
            item_id,
            corrections=body.corrections,
            ownership=body.ownership,
        )
        return await response_for(item, user_id)

    @router.get(
        "/{item_id}/image",
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_item_image(
        item_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        try:
            source = await application.read_display(user_id, item_id)
        except (FileNotFoundError, KeyError) as error:
            raise ItemSourceNotFoundError(item_id) from error
        return Response(
            content=source.body,
            media_type=source.content_type,
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{source.sha256}"',
            },
        )

    @router.get(
        "/{item_id}/source",
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_item_source(
        item_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        try:
            source = await application.read_source(user_id, item_id)
        except (FileNotFoundError, KeyError) as error:
            raise ItemSourceNotFoundError(item_id) from error
        return Response(
            content=source.body,
            media_type=source.content_type,
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{source.sha256}"',
            },
        )

    @router.delete(
        "/{item_id}/source",
        status_code=status.HTTP_204_NO_CONTENT,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def delete_item_source(
        item_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        await application.delete_source(user_id, item_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/{item_id}/retry",
        response_model=ItemRetryResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def retry_item(
        item_id: UUID,
        user_id: UUID = principal,
    ) -> ItemRetryResponse:
        job = await application.retry_item(user_id, item_id)
        return ItemRetryResponse(job_id=job.id, state=job.state, attempt=job.attempt)

    return router
