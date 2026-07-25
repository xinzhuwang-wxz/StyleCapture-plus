from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.ports import (
    JobRepository,
    ObjectStore,
)
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.features.wardrobe.demo import DemoWardrobeBootstrapper
from stylecapture_backend.main import BackendServices, create_app

SESSION_SECRET = "session-seed-quota-secret-with-enough-entropy"


class RecordingDemoWardrobe:
    def __init__(self) -> None:
        self.users: list[UUID] = []

    async def ensure_for_user(self, user_id: UUID) -> None:
        self.users.append(user_id)


def build_app(
    demo_wardrobe: RecordingDemoWardrobe,
    *,
    quota: int,
) -> object:
    unused = object()
    return create_app(
        BackendServices(
            capture=cast(CaptureApplication, unused),
            jobs=cast(JobRepository, unused),
            objects=cast(ObjectStore, unused),
            retries=cast(JobRetryApplication, unused),
            wardrobe=cast(WardrobeApplication, unused),
            demo_wardrobe=cast(DemoWardrobeBootstrapper, demo_wardrobe),
        ),
        session_signing_secret=SESSION_SECRET,
        demo_seed_new_session_quota=quota,
    )


@pytest.mark.asyncio
async def test_demo_seed_is_idempotent_per_cookie_and_bounded_for_new_sessions() -> None:
    demo_wardrobe = RecordingDemoWardrobe()
    app = build_app(demo_wardrobe, quota=2)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as first:
        first_response = await first.post("/v1/session")
        repeated_response = await first.post("/v1/session")
    async with AsyncClient(transport=transport, base_url="http://test") as second:
        second_response = await second.post("/v1/session")
    async with AsyncClient(transport=transport, base_url="http://test") as third:
        third_response = await third.post("/v1/session")

    first_user = UUID(first_response.json()["user_id"])
    assert repeated_response.json()["user_id"] == str(first_user)
    assert [first_response.status_code, repeated_response.status_code] == [201, 201]
    assert [second_response.status_code, third_response.status_code] == [201, 201]
    assert demo_wardrobe.users == [
        first_user,
        UUID(second_response.json()["user_id"]),
    ]
    assert UUID(third_response.json()["user_id"]) not in demo_wardrobe.users


def test_demo_seed_quota_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="quota must not be negative"):
        build_app(RecordingDemoWardrobe(), quota=-1)
