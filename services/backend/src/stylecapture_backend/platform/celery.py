from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]


def build_celery(redis_url: str) -> Celery:
    celery = Celery("stylecapture", broker=redis_url)
    celery.conf.update(
        accept_content=("json",),
        broker_connection_retry_on_startup=True,
        enable_utc=True,
        result_serializer="json",
        task_acks_late=True,
        task_ignore_result=True,
        task_reject_on_worker_lost=True,
        task_serializer="json",
        timezone="UTC",
        worker_prefetch_multiplier=1,
    )
    return celery
