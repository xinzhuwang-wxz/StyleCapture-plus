from __future__ import annotations

from typing import Any
from uuid import UUID

from stylecapture_backend.features.pixel_trial.ports import PIXEL_TRIAL_TASK_NAME


class PixelTrialDispatchError(RuntimeError):
    """The durable pixel trial exists, but the broker did not accept its task."""


class CeleryPixelTrialDispatcher:
    def __init__(self, celery: Any, *, queue: str) -> None:
        self._celery = celery
        self._queue = queue

    def enqueue_pixel_trial(self, *, user_id: UUID, trial_id: UUID) -> None:
        try:
            self._celery.send_task(
                PIXEL_TRIAL_TASK_NAME,
                kwargs={"user_id": str(user_id), "trial_id": str(trial_id)},
                queue=self._queue,
            )
        except Exception as error:
            raise PixelTrialDispatchError("Pixel trial task dispatch failed") from error
