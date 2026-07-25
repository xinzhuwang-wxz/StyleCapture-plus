from __future__ import annotations

import asyncio
from typing import Any, Protocol
from uuid import UUID

from stylecapture_backend.features.item_presentation.ports import ITEM_PRESENTATION_TASK_NAME
from stylecapture_backend.features.item_presentation.processing import (
    RetryableItemPresentationError,
)


class ItemPresentationProcessingService(Protocol):
    async def process(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        final_attempt: bool = False,
    ) -> None: ...


def register_item_presentation_task(
    celery: Any,
    processor: ItemPresentationProcessingService,
    *,
    max_retries: int = 2,
) -> Any:
    @celery.task(
        bind=True,
        name=ITEM_PRESENTATION_TASK_NAME,
        max_retries=max_retries,
        acks_late=True,
        reject_on_worker_lost=True,
    )
    def process_item_presentation(
        task: Any,
        *,
        user_id: str,
        asset_id: str,
    ) -> None:
        try:
            asyncio.run(
                processor.process(
                    user_id=UUID(user_id),
                    asset_id=UUID(asset_id),
                    final_attempt=int(task.request.retries) >= max_retries,
                )
            )
        except RetryableItemPresentationError as error:
            delay_seconds = min(30, 2 ** int(task.request.retries))
            raise task.retry(exc=error, countdown=delay_seconds) from error

    return process_item_presentation
