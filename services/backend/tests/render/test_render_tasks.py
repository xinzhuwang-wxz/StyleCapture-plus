from __future__ import annotations

from uuid import uuid4

import pytest
from stylecapture_backend.features.render.infrastructure.tasks import (
    RENDER_TASK_NAME,
    CeleryRenderDispatcher,
    RenderDispatchError,
)


class RecordingSender:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def send_task(
        self,
        name: str,
        *,
        kwargs: dict[str, object] | None = None,
        task_id: str | None = None,
        queue: str | None = None,
    ) -> object:
        if self.fail:
            raise ConnectionError("broker unavailable")
        self.calls.append(
            {
                "name": name,
                "kwargs": kwargs,
                "task_id": task_id,
                "queue": queue,
            }
        )
        return object()


def test_dispatcher_enqueues_user_scoped_render() -> None:
    sender = RecordingSender()
    dispatcher = CeleryRenderDispatcher(sender, queue="render-low")
    user_id = uuid4()
    artifact_id = uuid4()

    dispatcher.enqueue_render(user_id=user_id, artifact_id=artifact_id)

    assert sender.calls == [
        {
            "name": RENDER_TASK_NAME,
            "kwargs": {
                "user_id": str(user_id),
                "artifact_id": str(artifact_id),
            },
            "task_id": str(artifact_id),
            "queue": "render-low",
        }
    ]


def test_dispatcher_translates_broker_failures() -> None:
    dispatcher = CeleryRenderDispatcher(RecordingSender(fail=True))

    with pytest.raises(RenderDispatchError):
        dispatcher.enqueue_render(user_id=uuid4(), artifact_id=uuid4())
