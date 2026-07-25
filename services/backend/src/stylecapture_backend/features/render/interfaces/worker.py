from __future__ import annotations

import asyncio
from typing import Any, Protocol
from uuid import UUID

from stylecapture_backend.features.render.ports import RENDER_TASK_NAME
from stylecapture_backend.features.render.processing import RetryableRenderError


class RenderProcessingService(Protocol):
    async def process(self, *, user_id: UUID, artifact_id: UUID) -> None: ...


def register_render_task(
    celery: Any,
    processor: RenderProcessingService,
    *,
    max_retries: int = 2,
) -> Any:
    @celery.task(
        bind=True,
        name=RENDER_TASK_NAME,
        max_retries=max_retries,
        acks_late=True,
        reject_on_worker_lost=True,
    )
    def process_render(
        task: Any,
        *,
        user_id: str,
        artifact_id: str,
    ) -> None:
        try:
            asyncio.run(
                processor.process(
                    user_id=UUID(user_id),
                    artifact_id=UUID(artifact_id),
                )
            )
        except RetryableRenderError as error:
            delay_seconds = min(30, 2 ** int(task.request.retries))
            raise task.retry(exc=error, countdown=delay_seconds) from error

    return process_render
