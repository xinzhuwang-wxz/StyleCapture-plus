from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from kombu.exceptions import OperationalError  # type: ignore[import-untyped]

from stylecapture_backend.features.capture.ports import CAPTURE_TASK_NAME, JobDispatchError


class TaskSender(Protocol):
    def send_task(
        self,
        name: str,
        *,
        kwargs: dict[str, Any] | None = None,
        task_id: str | None = None,
        queue: str | None = None,
    ) -> object: ...


class CeleryJobDispatcher:
    def __init__(self, sender: TaskSender, *, queue: str = "capture") -> None:
        self._sender = sender
        self._queue = queue

    def enqueue_capture(self, capture_id: UUID, job_id: UUID) -> None:
        try:
            self._sender.send_task(
                CAPTURE_TASK_NAME,
                kwargs={"capture_id": str(capture_id), "job_id": str(job_id)},
                task_id=str(job_id),
                queue=self._queue,
            )
        except (OperationalError, ConnectionError, TimeoutError) as error:
            raise JobDispatchError("capture broker is unavailable") from error
