import asyncio
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from stylecapture_backend.features.look.domain import Look, PreferenceSignal
from stylecapture_backend.features.look.infrastructure.repository import SqlAlchemyLookRepository
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderInputSignature,
    RenderOutput,
    RenderPrivacy,
    RenderProviderTrace,
)
from stylecapture_backend.features.render.infrastructure.repository import (
    SqlAlchemyRenderArtifactRepository,
)
from stylecapture_backend.features.render.ports import RenderIdempotencyConflict
from stylecapture_backend.platform.database import build_session_factory, run_migrations

TEST_DATABASE_URL = os.environ.get(
    "STYLECAPTURE_TEST_DATABASE_URL",
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture_test",
)


async def insert_capture(
    *,
    sessions: async_sessionmaker[AsyncSession],
    user_id: UUID,
    suffix: str,
) -> UUID:
    capture_id = uuid4()
    async with sessions() as session:
        await session.execute(
            text(
                """
                INSERT INTO captures (
                    id, user_id, source_kind, object_key, sha256,
                    ownership, idempotency_key, created_at
                ) VALUES (
                    :capture_id, :user_id, 'feed', :object_key, :sha256,
                    'inspiration', :idempotency_key, now()
                )
                """
            ),
            {
                "capture_id": capture_id,
                "user_id": user_id,
                "object_key": f"originals/feed/render-{suffix}.png",
                "sha256": suffix[0] * 64,
                "idempotency_key": f"render-capture-{suffix}",
            },
        )
        await session.commit()
    return capture_id


async def insert_look(
    *,
    sessions: async_sessionmaker[AsyncSession],
    user_id: UUID,
    suffix: str,
) -> Look:
    capture_id = await insert_capture(sessions=sessions, user_id=user_id, suffix=suffix)
    looks = SqlAlchemyLookRepository(sessions)
    candidate = Look.feed_saved(
        user_id=user_id,
        capture_id=capture_id,
        source_selection_key=f"whole-{suffix}",
    )
    return await looks.ensure_placeholder(
        candidate,
        PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=candidate.id,
            idempotency_key=f"save-render-look-{suffix}",
        ),
    )


def signature(suffix: str = "a") -> RenderInputSignature:
    return RenderInputSignature(version="look-render-v1", hash=suffix * 64)


def output(suffix: str = "a") -> RenderOutput:
    return RenderOutput(
        object_key=f"derived/renders/{suffix}.webp",
        content_hash=suffix * 64,
        content_type="image/webp",
    )


@pytest.mark.asyncio
async def test_repository_persists_private_provider_trace_and_public_cache_hit() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE render_artifacts, preference_signals, look_components, "
                "looks, items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()

    user_id = uuid4()
    look = await insert_look(sessions=sessions, user_id=user_id, suffix="a")
    repository = SqlAlchemyRenderArtifactRepository(sessions)
    requested = await repository.ensure_requested(
        RenderArtifact.queued(
            user_id=user_id,
            look_id=look.id,
            kind=RenderArtifactKind.COLLAGE,
            input_signature=signature("a"),
            request_key="collage-a",
            provider_trace=RenderProviderTrace(
                provider="deterministic-collage",
                model="collage-v1",
                parameters={"layout": "grid"},
            ),
        )
    )
    stored = await repository.save(requested.mark_succeeded(output("a")))
    cached = await repository.find_cache_hit(
        look_id=look.id,
        kind=RenderArtifactKind.COLLAGE,
        input_signature=signature("a"),
    )

    assert cached == stored
    assert cached is not None
    assert cached.provider_trace is not None
    assert cached.provider_trace.provider == "deterministic-collage"
    assert cached.provider_trace.model == "collage-v1"
    assert dict(cached.provider_trace.parameters) == {"layout": "grid"}

    stale_running = requested.mark_running()
    preserved = await repository.save(stale_running)
    assert preserved.status.value == "succeeded"
    assert preserved.output == output("a")


@pytest.mark.asyncio
async def test_repository_rejects_request_key_reuse_for_different_inputs() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE render_artifacts, preference_signals, look_components, "
                "looks, items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()

    user_id = uuid4()
    look = await insert_look(sessions=sessions, user_id=user_id, suffix="b")
    repository = SqlAlchemyRenderArtifactRepository(sessions)
    await repository.ensure_requested(
        RenderArtifact.queued(
            user_id=user_id,
            look_id=look.id,
            kind=RenderArtifactKind.COLLAGE,
            input_signature=signature("b"),
            request_key="shared-render-request",
        )
    )

    with pytest.raises(RenderIdempotencyConflict):
        await repository.ensure_requested(
            RenderArtifact.queued(
                user_id=user_id,
                look_id=look.id,
                kind=RenderArtifactKind.COLLAGE,
                input_signature=signature("c"),
                request_key="shared-render-request",
            )
        )


@pytest.mark.asyncio
async def test_concurrent_equivalent_requests_share_one_active_artifact() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE render_artifacts, preference_signals, look_components, "
                "looks, items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()

    user_id = uuid4()
    look = await insert_look(sessions=sessions, user_id=user_id, suffix="c")
    repository = SqlAlchemyRenderArtifactRepository(sessions)
    first, second = await asyncio.gather(
        repository.ensure_requested(
            RenderArtifact.queued(
                user_id=user_id,
                look_id=look.id,
                kind=RenderArtifactKind.COLLAGE,
                input_signature=signature("c"),
                request_key="concurrent-render-one",
            )
        ),
        repository.ensure_requested(
            RenderArtifact.queued(
                user_id=user_id,
                look_id=look.id,
                kind=RenderArtifactKind.COLLAGE,
                input_signature=signature("c"),
                request_key="concurrent-render-two",
            )
        ),
    )

    assert first.id == second.id
    listed = await repository.list_for_look(user_id=user_id, look_id=look.id)
    assert [artifact.id for artifact in listed] == [first.id]


@pytest.mark.asyncio
async def test_repository_preserves_degraded_fallback_and_share_privacy() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE render_artifacts, preference_signals, look_components, "
                "looks, items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()

    user_id = uuid4()
    look = await insert_look(sessions=sessions, user_id=user_id, suffix="d")
    repository = SqlAlchemyRenderArtifactRepository(sessions)
    collage = await repository.ensure_requested(
        RenderArtifact.queued(
            user_id=user_id,
            look_id=look.id,
            kind=RenderArtifactKind.COLLAGE,
            input_signature=signature("d"),
            request_key="collage-d",
        )
    )
    collage = await repository.save(collage.mark_succeeded(output("d")))
    try_on = await repository.ensure_requested(
        RenderArtifact.queued(
            user_id=user_id,
            look_id=look.id,
            kind=RenderArtifactKind.TRY_ON,
            input_signature=signature("e"),
            request_key="try-on-d",
            source_artifact_id=collage.id,
        )
    )
    degraded = await repository.save(
        try_on.mark_degraded_to(fallback=collage, reason="provider timeout")
    )
    pixel = await repository.ensure_requested(
        RenderArtifact.queued(
            user_id=user_id,
            look_id=look.id,
            kind=RenderArtifactKind.PIXEL_COVER,
            input_signature=signature("f"),
            request_key="pixel-d",
            privacy=RenderPrivacy.SHAREABLE_PIXEL,
            source_artifact_id=collage.id,
        )
    )
    pixel = await repository.save(pixel.mark_succeeded(output("f")))
    listed = await repository.list_for_look(user_id=user_id, look_id=look.id)

    assert degraded.status == "degraded"
    assert degraded.fallback_artifact_id == collage.id
    assert degraded.output == collage.output
    assert degraded.share_eligible is False
    assert (
        await repository.find_cache_hit(
            look_id=look.id,
            kind=RenderArtifactKind.TRY_ON,
            input_signature=signature("e"),
        )
        is None
    )
    assert pixel.share_eligible is True
    assert [artifact.id for artifact in listed] == [collage.id, degraded.id, pixel.id]
    assert await repository.get_for_user(user_id=uuid4(), artifact_id=pixel.id) is None
