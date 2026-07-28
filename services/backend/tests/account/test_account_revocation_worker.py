from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from stylecapture_backend.features.account.interfaces.worker import (
    register_account_revocation_sweep_task,
)
from stylecapture_backend.features.account.ports import ACCOUNT_REVOCATION_SWEEP_TASK_NAME


class FakeCelery:
    def __init__(self) -> None:
        self.conf = SimpleNamespace(beat_schedule={})
        self.registered: dict[str, Any] = {}

    def task(self, **options: Any) -> Any:
        def decorate(function: Any) -> Any:
            self.registered[options["name"]] = {
                "function": function,
                "options": options,
            }
            return function

        return decorate


class UnusedProcessor:
    async def process_apple_provider_revocations(
        self,
        *,
        lease_owner: str | None = None,
        limit: int = 25,
    ) -> int:
        del lease_owner, limit
        return 0


def test_account_revocation_sweep_uses_configured_queue_and_schedule() -> None:
    celery = FakeCelery()

    register_account_revocation_sweep_task(
        celery,
        UnusedProcessor(),
        max_retries=3,
        queue="account-maintenance",
        schedule_seconds=45,
    )

    assert celery.registered[ACCOUNT_REVOCATION_SWEEP_TASK_NAME]["options"]["max_retries"] == 3
    schedule = celery.conf.beat_schedule["stylecapture-account-revocation-sweep"]
    assert schedule == {
        "task": ACCOUNT_REVOCATION_SWEEP_TASK_NAME,
        "schedule": 45,
        "kwargs": {"limit": 25},
        "options": {"queue": "account-maintenance"},
    }
