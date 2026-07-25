from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from stylecapture_backend.features.pixel_trial.domain import PixelTrial, PixelTrialStatus
from stylecapture_backend.features.pixel_trial.ports import (
    PixelTrialNotFound,
    PixelTrialRepository,
)
from stylecapture_backend.features.render.domain import RenderOutput, RenderProviderTrace


@dataclass(frozen=True, slots=True)
class PixelTrialView:
    id: UUID
    user_id: UUID
    status: PixelTrialStatus
    request_key: str
    object_key: str | None
    content_hash: str | None
    content_type: str | None
    subject_object_key: str | None
    subject_attached: bool
    failure_message: str | None
    created_at: datetime
    updated_at: datetime
    dispatch_required: bool = False


class PixelTrialApplication:
    def __init__(self, *, trials: PixelTrialRepository) -> None:
        self._trials = trials

    async def create_or_get(
        self,
        *,
        user_id: UUID,
        subject_object_key: str,
        request_key: str,
    ) -> PixelTrialView:
        trial = PixelTrial.queued(
            user_id=user_id,
            subject_object_key=subject_object_key,
            request_key=request_key,
        )
        stored = await self._trials.ensure_requested(trial)
        return _view(stored, dispatch_required=stored.status is PixelTrialStatus.QUEUED)

    async def get(self, *, user_id: UUID, trial_id: UUID) -> PixelTrialView:
        trial = await self._trials.get_for_user(user_id=user_id, trial_id=trial_id)
        if trial is None:
            raise PixelTrialNotFound("Pixel trial not found")
        return _view(trial)

    async def delete(self, *, user_id: UUID, trial_id: UUID) -> PixelTrialView:
        trial = await self._trials.delete_for_user(user_id=user_id, trial_id=trial_id)
        if trial is None:
            raise PixelTrialNotFound("Pixel trial not found")
        return _view(trial)

    async def forget_subject_photo(self, *, user_id: UUID, trial_id: UUID) -> PixelTrialView:
        trial = await self._require_trial(user_id=user_id, trial_id=trial_id)
        return _view(await self._trials.save(trial.forget_subject_photo()))

    async def mark_running(
        self,
        *,
        user_id: UUID,
        trial_id: UUID,
        provider_trace: RenderProviderTrace | None = None,
    ) -> PixelTrialView:
        trial = await self._require_trial(user_id=user_id, trial_id=trial_id)
        return _view(await self._trials.save(trial.mark_running(provider_trace)))

    async def mark_succeeded(
        self,
        *,
        user_id: UUID,
        trial_id: UUID,
        output: RenderOutput,
        provider_trace: RenderProviderTrace,
    ) -> PixelTrialView:
        trial = await self._require_trial(user_id=user_id, trial_id=trial_id)
        return _view(
            await self._trials.save(
                trial.mark_succeeded(output=output, provider_trace=provider_trace)
            )
        )

    async def mark_failed(
        self,
        *,
        user_id: UUID,
        trial_id: UUID,
        code: str,
        message: str,
    ) -> PixelTrialView:
        trial = await self._require_trial(user_id=user_id, trial_id=trial_id)
        return _view(await self._trials.save(trial.mark_failed(code=code, message=message)))

    async def _require_trial(self, *, user_id: UUID, trial_id: UUID) -> PixelTrial:
        trial = await self._trials.get_for_user(user_id=user_id, trial_id=trial_id)
        if trial is None:
            raise PixelTrialNotFound("Pixel trial not found")
        return trial


def _view(trial: PixelTrial, *, dispatch_required: bool = False) -> PixelTrialView:
    return PixelTrialView(
        id=trial.id,
        user_id=trial.user_id,
        status=trial.status,
        request_key=trial.request_key,
        object_key=trial.output.object_key if trial.output is not None else None,
        content_hash=trial.output.content_hash if trial.output is not None else None,
        content_type=trial.output.content_type if trial.output is not None else None,
        subject_object_key=trial.subject_object_key,
        subject_attached=trial.subject_object_key is not None,
        failure_message=trial.failure_message,
        created_at=trial.created_at,
        updated_at=trial.updated_at,
        dispatch_required=dispatch_required,
    )
