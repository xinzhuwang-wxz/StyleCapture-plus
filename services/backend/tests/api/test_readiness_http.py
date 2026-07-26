from __future__ import annotations

from typing import cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.ports import JobRepository, ObjectStore
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.main import BackendServices, create_app


def _app_with_readiness(checks: dict[str, bool]) -> FastAPI:
    unused = object()
    return create_app(
        BackendServices(
            capture=cast(CaptureApplication, unused),
            jobs=cast(JobRepository, unused),
            objects=cast(ObjectStore, unused),
            retries=cast(JobRetryApplication, unused),
            wardrobe=cast(WardrobeApplication, unused),
        ),
        readiness_check=lambda: _return_checks(checks),
    )


async def _return_checks(checks: dict[str, bool]) -> dict[str, bool]:
    return checks


@pytest.mark.asyncio
async def test_readyz_returns_ok_when_all_dependencies_are_available() -> None:
    app = _app_with_readiness({"database": True, "redis": True, "litellm": True})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": True, "redis": True, "litellm": True},
    }


@pytest.mark.asyncio
async def test_readyz_returns_503_when_a_dependency_is_unavailable() -> None:
    app = _app_with_readiness({"database": True, "redis": False, "litellm": True})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": True, "redis": False, "litellm": True},
    }
