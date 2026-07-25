from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from stylecapture_backend.features.outfit.domain import (
    OutfitWorkflowStatus,
    OutfitWorkflowTrace,
)
from stylecapture_backend.features.outfit.infrastructure.repository import (
    SqlAlchemyOutfitWorkflowTraceRepository,
)
from stylecapture_backend.platform.database import build_session_factory, run_migrations

TEST_DATABASE_URL = os.environ.get(
    "STYLECAPTURE_TEST_DATABASE_URL",
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture_test",
)


@pytest.mark.asyncio
async def test_workflow_trace_repository_upserts_and_scopes_by_user() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE outfit_workflow_traces"))
        await session.commit()

    repository = SqlAlchemyOutfitWorkflowTraceRepository(sessions)
    user_id = uuid4()
    trace_id = uuid4()
    request_id = uuid4()
    started = datetime.now(UTC)
    initial = OutfitWorkflowTrace(
        id=trace_id,
        user_id=user_id,
        request_id=request_id,
        status=OutfitWorkflowStatus.CANDIDATES_READY,
        explanation_state="rule_ranked",
        plan_count=4,
        capability_alias="deterministic_rules",
        model_version="outfit-plan-rules-v1",
        created_at=started,
        updated_at=started,
    )
    await repository.save(initial)
    await repository.save(
        OutfitWorkflowTrace(
            id=trace_id,
            user_id=user_id,
            request_id=request_id,
            status=OutfitWorkflowStatus.COMPLETED,
            explanation_state="llm_ranked",
            plan_count=4,
            capability_alias="reasoning",
            model_version="outfit-rerank-model-v1",
            created_at=started + timedelta(seconds=1),
            updated_at=started + timedelta(seconds=1),
        )
    )

    stored = await repository.get_for_user(trace_id=trace_id, user_id=user_id)

    assert stored is not None
    assert stored.status is OutfitWorkflowStatus.COMPLETED
    assert stored.created_at == started
    assert stored.updated_at == started + timedelta(seconds=1)
    assert stored.capability_alias == "reasoning"
    assert await repository.get_for_user(trace_id=trace_id, user_id=uuid4()) is None
