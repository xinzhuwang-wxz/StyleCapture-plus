from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from pydantic import BaseModel
from stylecapture_backend.features.capture.ports import ObjectStore
from stylecapture_backend.features.item_presentation.application import (
    ItemPresentationApplication,
    ItemPresentationView,
)
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationKind,
    ItemPresentationStatus,
)
from stylecapture_backend.features.item_presentation.ports import ItemPresentationNotFound
from stylecapture_backend.platform.errors import STABLE_ERROR_RESPONSES


class ItemPresentationDispatcher(Protocol):
    def enqueue_item_presentation(self, *, user_id: UUID, asset_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class ItemPresentationHttpServices:
    presentations: ItemPresentationApplication
    objects: ObjectStore
    dispatcher: ItemPresentationDispatcher | None = None


class ItemPresentationResponse(BaseModel):
    id: UUID
    item_id: UUID
    kind: ItemPresentationKind
    status: ItemPresentationStatus
    output_image_url: str | None
    failure_code: str | None
    failure_message: str | None
    retryable: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_view(cls, view: ItemPresentationView) -> ItemPresentationResponse:
        return cls(
            id=view.id,
            item_id=view.item_id,
            kind=view.kind,
            status=view.status,
            output_image_url=(
                f"/v1/item-presentations/{view.id}/image" if view.object_key is not None else None
            ),
            failure_code=view.failure_code,
            failure_message=(
                "像素单品图暂时没有生成。可以重试。" if view.failure_code is not None else None
            ),
            retryable=view.status is ItemPresentationStatus.FAILED,
            created_at=view.created_at,
            updated_at=view.updated_at,
        )


def build_item_presentation_router(
    services: ItemPresentationHttpServices,
    *,
    current_user: Callable[..., UUID],
) -> APIRouter:
    router = APIRouter()
    principal = Depends(current_user)

    @router.post(
        "/v1/items/{item_id}/presentations/pixel",
        response_model=ItemPresentationResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def ensure_item_pixel_presentation(
        item_id: UUID,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        user_id: UUID = principal,
    ) -> ItemPresentationResponse:
        view = await services.presentations.ensure_pixel_item(
            user_id=user_id,
            item_id=item_id,
            request_key=idempotency_key,
        )
        if (
            services.dispatcher is not None
            and view.dispatch_required
            and view.status is ItemPresentationStatus.QUEUED
        ):
            services.dispatcher.enqueue_item_presentation(user_id=view.user_id, asset_id=view.id)
        return ItemPresentationResponse.from_view(view)

    @router.post(
        "/v1/items/{item_id}/presentations/pixel/retry",
        response_model=ItemPresentationResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def retry_item_pixel_presentation(
        item_id: UUID,
        user_id: UUID = principal,
    ) -> ItemPresentationResponse:
        view = await services.presentations.retry_pixel_item(
            user_id=user_id,
            item_id=item_id,
        )
        if (
            services.dispatcher is not None
            and view.dispatch_required
            and view.status is ItemPresentationStatus.QUEUED
        ):
            services.dispatcher.enqueue_item_presentation(
                user_id=view.user_id,
                asset_id=view.id,
            )
        return ItemPresentationResponse.from_view(view)

    @router.get(
        "/v1/item-presentations/{asset_id}",
        response_model=ItemPresentationResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_item_presentation(
        asset_id: UUID,
        user_id: UUID = principal,
    ) -> ItemPresentationResponse:
        return ItemPresentationResponse.from_view(
            await services.presentations.get(user_id=user_id, asset_id=asset_id)
        )

    @router.get(
        "/v1/item-presentations/{asset_id}/image",
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_item_presentation_image(
        asset_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        view = await services.presentations.get(user_id=user_id, asset_id=asset_id)
        if view.object_key is None:
            raise ItemPresentationNotFound("Item presentation image is not ready")
        try:
            stored = services.objects.describe(view.object_key)
            body = services.objects.read(view.object_key)
        except (FileNotFoundError, KeyError) as error:
            raise ItemPresentationNotFound("Item presentation image is unavailable") from error
        return Response(
            content=body,
            media_type=stored.content_type,
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{stored.sha256}"',
            },
        )

    return router
