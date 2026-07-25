from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from kombu.exceptions import OperationalError  # type: ignore[import-untyped]

from stylecapture_backend.features.render.ports import RENDER_TASK_NAME


class RenderDispatchError(RuntimeError):
    """The render request exists, but the broker did not accept its task."""


class TaskSender(Protocol):
    def send_task(
        self,
        name: str,
        *,
        kwargs: dict[str, Any] | None = None,
        task_id: str | None = None,
        queue: str | None = None,
    ) -> object: ...


class CeleryRenderDispatcher:
    def __init__(self, sender: TaskSender, *, queue: str = "render") -> None:
        self._sender = sender
        self._queue = queue

    def enqueue_render(self, *, user_id: UUID, artifact_id: UUID) -> None:
        try:
            self._sender.send_task(
                RENDER_TASK_NAME,
                kwargs={
                    "user_id": str(user_id),
                    "artifact_id": str(artifact_id),
                },
                task_id=str(artifact_id),
                queue=self._queue,
            )
        except (OperationalError, ConnectionError, TimeoutError) as error:
            raise RenderDispatchError("render broker is unavailable") from error
