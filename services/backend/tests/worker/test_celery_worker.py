from uuid import UUID, uuid4

from stylecapture_backend.features.capture.domain import JobState
from stylecapture_backend.features.capture.interfaces.worker import register_capture_task
from stylecapture_backend.features.capture.processing import (
    ProcessingOutcome,
    ProviderError,
)
from stylecapture_backend.platform.celery import build_celery


class SequencedProcessor:
    def __init__(self, outcomes: list[ProcessingOutcome]) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[UUID, UUID]] = []

    async def process(self, capture_id: UUID, job_id: UUID) -> ProcessingOutcome:
        self.calls.append((capture_id, job_id))
        return self.outcomes.pop(0)


def test_worker_retries_a_retryable_partial_outcome_with_the_same_ids() -> None:
    celery = build_celery("memory://")
    celery.conf.update(task_always_eager=True, task_eager_propagates=False)
    processor = SequencedProcessor(
        [
            ProcessingOutcome.partial(
                ProviderError(
                    "embedding_unavailable",
                    "embedding unavailable",
                    retryable=True,
                )
            ),
            ProcessingOutcome.ready(),
        ]
    )
    task = register_capture_task(celery, processor, max_retries=2)
    capture_id = uuid4()
    job_id = uuid4()

    result = task.apply(kwargs={"capture_id": str(capture_id), "job_id": str(job_id)}).get()

    assert result == {"state": "ready", "error_code": None}
    assert processor.calls == [(capture_id, job_id), (capture_id, job_id)]


def test_worker_does_not_retry_a_nonretryable_provider_contract_failure() -> None:
    celery = build_celery("memory://")
    celery.conf.update(task_always_eager=True, task_eager_propagates=True)
    processor = SequencedProcessor(
        [
            ProcessingOutcome(
                state=JobState.ERROR,
                retryable=False,
                error_code="vision_schema_invalid",
            )
        ]
    )
    task = register_capture_task(celery, processor, max_retries=2)

    result = task.apply(kwargs={"capture_id": str(uuid4()), "job_id": str(uuid4())}).get()

    assert result == {
        "state": "error",
        "error_code": "vision_schema_invalid",
    }
    assert len(processor.calls) == 1
