from __future__ import annotations

import asyncio
from typing import Any, Protocol
from uuid import UUID

from stylecapture_backend.features.capture.infrastructure.tasks import CAPTURE_TASK_NAME
from stylecapture_backend.features.capture.processing import ProcessingOutcome


class CaptureProcessingService(Protocol):
    async def process(self, capture_id: UUID, job_id: UUID) -> ProcessingOutcome: ...


class RetryableProcessingError(RuntimeError):
    pass


def register_capture_task(
    celery: Any,
    processor: CaptureProcessingService,
    *,
    max_retries: int = 2,
) -> Any:
    @celery.task(
        bind=True,
        name=CAPTURE_TASK_NAME,
        max_retries=max_retries,
        acks_late=True,
        reject_on_worker_lost=True,
    )
    def process_capture(
        task: Any,
        *,
        capture_id: str,
        job_id: str,
    ) -> dict[str, str | None]:
        outcome = asyncio.run(
            processor.process(
                UUID(capture_id),
                UUID(job_id),
            )
        )
        if outcome.retryable and outcome.error_code is not None:
            delay_seconds = min(30, 2 ** int(task.request.retries))
            raise task.retry(
                exc=RetryableProcessingError(outcome.error_code),
                countdown=delay_seconds,
            )
        return {
            "state": outcome.state.value,
            "error_code": outcome.error_code,
        }

    return process_capture
