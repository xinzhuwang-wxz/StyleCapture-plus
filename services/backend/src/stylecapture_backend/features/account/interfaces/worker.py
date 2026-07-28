from __future__ import annotations

import asyncio
from typing import Any, Protocol

from stylecapture_backend.features.account.ports import ACCOUNT_REVOCATION_SWEEP_TASK_NAME


class AppleProviderRevocationProcessor(Protocol):
    async def process_apple_provider_revocations(
        self,
        *,
        lease_owner: str | None = None,
        limit: int = 25,
    ) -> int: ...


def register_account_revocation_sweep_task(
    celery: Any,
    processor: AppleProviderRevocationProcessor,
    *,
    max_retries: int = 2,
    queue: str,
    schedule_seconds: float,
) -> Any:
    @celery.task(
        bind=True,
        name=ACCOUNT_REVOCATION_SWEEP_TASK_NAME,
        max_retries=max_retries,
        acks_late=True,
        reject_on_worker_lost=True,
    )
    def sweep_apple_provider_revocations(
        task: Any,
        *,
        limit: int = 25,
    ) -> dict[str, int]:
        processed = asyncio.run(
            processor.process_apple_provider_revocations(
                lease_owner=str(task.request.id),
                limit=limit,
            )
        )
        return {"processed": processed}

    celery.conf.beat_schedule = {
        **getattr(celery.conf, "beat_schedule", {}),
        "stylecapture-account-revocation-sweep": {
            "task": ACCOUNT_REVOCATION_SWEEP_TASK_NAME,
            "schedule": schedule_seconds,
            "kwargs": {"limit": 25},
            "options": {"queue": queue},
        },
    }
    return sweep_apple_provider_revocations
