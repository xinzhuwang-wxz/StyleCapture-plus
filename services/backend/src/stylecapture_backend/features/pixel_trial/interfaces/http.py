from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from pydantic import BaseModel
from stylecapture_backend.features.capture.ports import ObjectStore
from stylecapture_backend.features.pixel_trial.application import (
    PixelTrialApplication,
    PixelTrialView,
)
from stylecapture_backend.features.pixel_trial.domain import PixelTrialStatus
from stylecapture_backend.features.pixel_trial.ports import PixelTrialNotFound
from stylecapture_backend.platform.errors import STABLE_ERROR_RESPONSES


class PixelTrialDispatcher(Protocol):
    def enqueue_pixel_trial(self, *, user_id: UUID, trial_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class PixelTrialHttpServices:
    trials: PixelTrialApplication
    objects: ObjectStore
    dispatcher: PixelTrialDispatcher | None = None


class CreatePixelTrialBody(BaseModel):
    subject_object_key: str


class PixelTrialResponse(BaseModel):
    id: UUID
    status: PixelTrialStatus
    subject_attached: bool
    output_image_url: str | None
    sprite_image_url: str | None
    failure_code: str | None
    failure_message: str | None
    retryable: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_view(cls, view: PixelTrialView) -> PixelTrialResponse:
        return cls(
            id=view.id,
            status=view.status,
            subject_attached=view.subject_attached,
            output_image_url=(
                f"/v1/pixel-trials/{view.id}/image" if view.object_key is not None else None
            ),
            sprite_image_url=(
                f"/v1/pixel-trials/{view.id}/sprite"
                if view.sprite_object_key is not None
                else None
            ),
            failure_code=view.failure_code,
            failure_message=(
                "像素形象暂时没有生成。可以重试。" if view.failure_code is not None else None
            ),
            retryable=view.status is PixelTrialStatus.FAILED and view.subject_attached,
            created_at=view.created_at,
            updated_at=view.updated_at,
        )


def build_pixel_trial_router(
    services: PixelTrialHttpServices,
    *,
    current_user: Callable[..., UUID],
) -> APIRouter:
    router = APIRouter()
    principal = Depends(current_user)

    @router.post(
        "/v1/pixel-trials",
        response_model=PixelTrialResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def create_pixel_trial(
        body: CreatePixelTrialBody,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        user_id: UUID = principal,
    ) -> PixelTrialResponse:
        try:
            subject = services.objects.describe(body.subject_object_key)
        except (FileNotFoundError, KeyError) as error:
            raise PixelTrialNotFound("Pixel trial subject photo does not exist") from error
        if subject.owner_id != user_id:
            raise PixelTrialNotFound("Pixel trial subject photo does not exist")
        view = await services.trials.create_or_get(
            user_id=user_id,
            subject_object_key=body.subject_object_key,
            request_key=idempotency_key,
        )
        services.objects.mark_attached(body.subject_object_key, user_id)
        if (
            services.dispatcher is not None
            and view.dispatch_required
            and view.status is PixelTrialStatus.QUEUED
        ):
            services.dispatcher.enqueue_pixel_trial(user_id=view.user_id, trial_id=view.id)
        return PixelTrialResponse.from_view(view)

    @router.get(
        "/v1/pixel-trials/{trial_id}",
        response_model=PixelTrialResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_pixel_trial(
        trial_id: UUID,
        user_id: UUID = principal,
    ) -> PixelTrialResponse:
        return PixelTrialResponse.from_view(
            await services.trials.get(user_id=user_id, trial_id=trial_id)
        )

    @router.get(
        "/v1/pixel-trials/{trial_id}/image",
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_pixel_trial_image(
        trial_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        view = await services.trials.get(user_id=user_id, trial_id=trial_id)
        if view.object_key is None:
            raise PixelTrialNotFound("Pixel trial image is not ready")
        try:
            stored = services.objects.describe(view.object_key)
            body = services.objects.read(view.object_key)
        except (FileNotFoundError, KeyError) as error:
            raise PixelTrialNotFound("Pixel trial image is unavailable") from error
        return Response(
            content=body,
            media_type=stored.content_type,
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{stored.sha256}"',
            },
        )

    @router.get(
        "/v1/pixel-trials/{trial_id}/sprite",
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_pixel_trial_sprite(
        trial_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        view = await services.trials.get(user_id=user_id, trial_id=trial_id)
        if view.sprite_object_key is None:
            raise PixelTrialNotFound("Pixel trial sprite is not ready")
        try:
            stored = services.objects.describe(view.sprite_object_key)
            body = services.objects.read(view.sprite_object_key)
        except (FileNotFoundError, KeyError) as error:
            raise PixelTrialNotFound("Pixel trial sprite is unavailable") from error
        return Response(
            content=body,
            media_type=stored.content_type,
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"{stored.sha256}"',
            },
        )

    @router.delete(
        "/v1/pixel-trials/{trial_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def delete_pixel_trial(
        trial_id: UUID,
        user_id: UUID = principal,
    ) -> Response:
        view = await services.trials.delete(user_id=user_id, trial_id=trial_id)
        if view.object_key is not None:
            services.objects.delete(view.object_key)
        if view.sprite_object_key is not None and view.sprite_object_key != view.object_key:
            services.objects.delete(view.sprite_object_key)
        if view.subject_object_key is not None and view.subject_object_key != view.object_key:
            services.objects.delete(view.subject_object_key)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
