from unittest.mock import Mock
from uuid import uuid4

import pytest
from stylecapture_backend.features.capture.infrastructure.tasks import (
    CAPTURE_TASK_NAME,
    CeleryJobDispatcher,
)
from stylecapture_backend.features.capture.ports import JobDispatchError
from stylecapture_backend.platform.celery import build_celery


def test_dispatcher_sends_a_json_task_with_a_stable_job_identity() -> None:
    sender = Mock()
    capture_id = uuid4()
    job_id = uuid4()
    dispatcher = CeleryJobDispatcher(sender)

    dispatcher.enqueue_capture(capture_id, job_id)

    sender.send_task.assert_called_once_with(
        CAPTURE_TASK_NAME,
        kwargs={"capture_id": str(capture_id), "job_id": str(job_id)},
        task_id=str(job_id),
        queue="capture",
    )


def test_dispatcher_exposes_broker_failure_as_a_retryable_port_error() -> None:
    sender = Mock()
    sender.send_task.side_effect = ConnectionError("redis unavailable")
    dispatcher = CeleryJobDispatcher(sender)

    with pytest.raises(JobDispatchError):
        dispatcher.enqueue_capture(uuid4(), uuid4())


def test_celery_transport_only_accepts_json_and_limits_worker_prefetch() -> None:
    celery = build_celery("redis://redis:6379/0")

    assert celery.conf.accept_content == ("json",)
    assert celery.conf.task_serializer == "json"
    assert celery.conf.worker_prefetch_multiplier == 1
    assert celery.conf.task_acks_late is True
