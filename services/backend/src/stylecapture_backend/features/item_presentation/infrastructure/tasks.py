from __future__ import annotations

from typing import Any
from uuid import UUID

from kombu.exceptions import OperationalError  # type: ignore[import-untyped]
from stylecapture_backend.features.item_presentation.ports import (
    ITEM_PRESENTATION_TASK_NAME,
    ItemPresentationDispatchError,
)


class CeleryItemPresentationDispatcher:
    def __init__(self, celery: Any, *, queue: str) -> None:
        self._celery = celery
        self._queue = queue

    def enqueue_item_presentation(self, *, user_id: UUID, asset_id: UUID) -> None:
        try:
            self._celery.send_task(
                ITEM_PRESENTATION_TASK_NAME,
                kwargs={"user_id": str(user_id), "asset_id": str(asset_id)},
                task_id=str(asset_id),
                queue=self._queue,
            )
        except (OperationalError, ConnectionError, TimeoutError) as error:
            raise ItemPresentationDispatchError("Item presentation task dispatch failed") from error
