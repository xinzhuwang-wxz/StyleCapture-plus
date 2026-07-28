from __future__ import annotations

from collections import Counter
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.ports import JobRepository, ObjectStore
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.main import BackendServices, create_app
from stylecapture_backend.platform.cost_guard import (
    CostGuardLease,
    costly_capability,
)


class RecordingCostGuard:
    def __init__(self, limits: dict[str, int]) -> None:
        self._limits = limits
        self._counts: Counter[tuple[str, str]] = Counter()
        self.requests: list[tuple[str, str | None, str]] = []

    async def acquire(
        self,
        *,
        client_key: str,
        actor_key: str | None,
        capability: str,
    ) -> CostGuardLease:
        self.requests.append((client_key, actor_key, capability))
        key = (client_key, capability)
        self._counts[key] += 1
        allowed = self._counts[key] <= self._limits.get(capability, 100)
        return CostGuardLease(allowed=allowed, retry_after_seconds=17)

    async def release(self, lease: CostGuardLease) -> None:
        del lease


def build_app(cost_guard: RecordingCostGuard) -> object:
    unused = object()
    return create_app(
        BackendServices(
            capture=cast(CaptureApplication, unused),
            jobs=cast(JobRepository, unused),
            objects=cast(ObjectStore, unused),
            retries=cast(JobRetryApplication, unused),
            wardrobe=cast(WardrobeApplication, unused),
        ),
        session_signing_secret="cost-guard-test-session-secret-with-enough-entropy",
        cost_guard=cost_guard,
    )


@pytest.mark.asyncio
async def test_session_creation_is_not_rate_limited_as_ai_work() -> None:
    guard = RecordingCostGuard({})
    app = build_app(guard)
    transport = ASGITransport(app=app, client=("203.0.113.9", 4567))  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as first:
        accepted = await first.post("/v1/session")
    async with AsyncClient(transport=transport, base_url="http://test") as second:
        accepted_again = await second.post("/v1/session")

    assert accepted.status_code == 201
    assert accepted_again.status_code == 201
    assert guard.requests == []


@pytest.mark.asyncio
async def test_authenticated_capability_is_scoped_to_client_and_signed_session() -> None:
    guard = RecordingCostGuard({"reasoning": 0})
    app = build_app(guard)
    transport = ASGITransport(app=app, client=("10.0.0.5", 4567))  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        session = await client.post(
            "/v1/session",
            headers={"X-Forwarded-For": "198.51.100.12"},
        )
        limited = await client.post(
            "/v1/outfit-plans/stream",
            json={},
            headers={"X-Forwarded-For": "198.51.100.12"},
        )

    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "17"
    assert guard.requests[-1] == (
        "198.51.100.12",
        session.json()["user_id"],
        "reasoning",
    )


@pytest.mark.asyncio
async def test_untrusted_peer_cannot_spoof_forwarded_client_address() -> None:
    guard = RecordingCostGuard({})
    app = build_app(guard)
    transport = ASGITransport(app=app, client=("8.8.8.8", 4567))  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/captures",
            json={},
            headers={"X-Forwarded-For": "192.0.2.99"},
        )

    assert response.status_code in {401, 422}
    assert guard.requests[0][0] == "8.8.8.8"


def test_saving_a_plan_is_not_charged_to_the_ai_budget() -> None:
    """Saving verifies a signed ticket and writes rows — it calls no model.

    Charging it to `reasoning` also charged it against per-actor concurrency
    (1), so a save issued straight after the planning stream was refused while
    that stream's lease was still unwinding, and the user was told the outfit
    "暂时没有保存" for what is a pure database write.
    """

    assert costly_capability("POST", "/v1/outfit-plans") == "reasoning"
    assert costly_capability("POST", "/v1/outfit-plans/stream") == "reasoning"
    assert costly_capability("POST", "/v1/outfit-plans/abc/replace-slot") == "reasoning"
    assert costly_capability("POST", "/v1/outfit-plans/abc/save-look") is None
