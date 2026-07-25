from __future__ import annotations

import asyncio
import os
from contextlib import suppress

import asyncpg  # type: ignore[import-untyped]
import pytest
from sqlalchemy.engine import make_url

LOCAL_TEST_DATABASE_URL = (
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture_test"
)

# Repository tests truncate tables by design. Keep them on a database that can never be
# mistaken for the locally running product database.
os.environ.setdefault("STYLECAPTURE_TEST_DATABASE_URL", LOCAL_TEST_DATABASE_URL)
configured_test_url = make_url(os.environ["STYLECAPTURE_TEST_DATABASE_URL"])
if (
    configured_test_url.database is None
    or not configured_test_url.database.endswith("_test")
    or configured_test_url.database == "stylecapture"
):
    raise RuntimeError(
        "STYLECAPTURE_TEST_DATABASE_URL must name an isolated database ending in '_test'"
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    del session
    if os.environ["STYLECAPTURE_TEST_DATABASE_URL"] != LOCAL_TEST_DATABASE_URL:
        return
    asyncio.run(_ensure_local_test_database())


async def _ensure_local_test_database() -> None:
    connection = await asyncpg.connect(
        user="stylecapture",
        password="stylecapture",
        host="127.0.0.1",
        port=5434,
        database="postgres",
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'stylecapture_test'"
        )
        if exists is None:
            with suppress(asyncpg.DuplicateDatabaseError):
                await connection.execute("CREATE DATABASE stylecapture_test OWNER stylecapture")
    finally:
        await connection.close()
