from __future__ import annotations

import asyncio
from typing import Any, Protocol
from uuid import UUID

from stylecapture_backend.features.pixel_trial.ports import PIXEL_TRIAL_TASK_NAME
from stylecapture_backend.features.pixel_trial.processing import RetryablePixelTrialError


class PixelTrialProcessingService(Protocol):
    async def process(
        self,
        *,
        user_id: UUID,
        trial_id: UUID,
        final_attempt: bool = False,
    ) -> None: ...


def register_pixel_trial_task(
    celery: Any,
    processor: PixelTrialProcessingService,
    *,
    max_retries: int = 2,
) -> Any:
    @celery.task(
        bind=True,
        name=PIXEL_TRIAL_TASK_NAME,
        max_retries=max_retries,
        acks_late=True,
        reject_on_worker_lost=True,
    )
    def process_pixel_trial(
        task: Any,
        *,
        user_id: str,
        trial_id: str,
    ) -> None:
        try:
            asyncio.run(
                processor.process(
                    user_id=UUID(user_id),
                    trial_id=UUID(trial_id),
                    final_attempt=int(task.request.retries) >= max_retries,
                )
            )
        except RetryablePixelTrialError as error:
            delay_seconds = min(30, 2 ** int(task.request.retries))
            raise task.retry(exc=error, countdown=delay_seconds) from error

    return process_pixel_trial
