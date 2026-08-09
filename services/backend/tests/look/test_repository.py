import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from stylecapture_backend.features.capture.domain import NormalizedPoint
from stylecapture_backend.features.look.domain import (
    COMPOSITION_ITEM_EVIDENCE,
    Look,
    LookAnalysis,
    LookAnalysisField,
    LookAnalysisMetadata,
    LookComponent,
    PreferenceSignal,
)
from stylecapture_backend.features.look.infrastructure.repository import (
    SqlAlchemyLookRepository,
)
from stylecapture_backend.features.look.ports import PreferenceIdempotencyConflict
from stylecapture_backend.platform.database import build_session_factory, run_migrations

TEST_DATABASE_URL = os.environ.get(
    "STYLECAPTURE_TEST_DATABASE_URL",
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture_test",
)


def composition_analysis() -> LookAnalysis:
    field = LookAnalysisField(value="简洁通勤", confidence=0.9)
    return LookAnalysis(
        color=field,
        silhouette=field,
        material=field,
        layering=field,
        focal_point=field,
        scene=field,
        style=field,
        metadata=LookAnalysisMetadata(
            capability_alias="reasoning",
            model_version="test",
            prompt_version="v1",
            schema_version="v1",
            taxonomy_version="v1",
            latency_ms=1,
        ),
    )


async def insert_capture_and_item(
    *,
    sessions: async_sessionmaker[AsyncSession],
    user_id: UUID,
    suffix: str,
) -> tuple[UUID, UUID]:
    capture_id = uuid4()
    item_id = uuid4()
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
                "object_key": f"originals/feed/{suffix}.png",
                "sha256": suffix[0] * 64,
                "idempotency_key": f"capture-{suffix}",
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO items (
                    id, user_id, capture_id, selection_key, source_object_key,
                    source_available, ownership, status, attributes, model_metadata,
                    created_at, updated_at
                ) VALUES (
                    :item_id, :user_id, :capture_id, :selection_key, :object_key,
                    true, 'inspiration', 'ready', '{}'::jsonb, '{}'::jsonb,
                    now(), now()
                )
                """
            ),
            {
                "capture_id": capture_id,
                "item_id": item_id,
                "user_id": user_id,
                "object_key": f"originals/feed/{suffix}.png",
                "selection_key": f"item-{suffix}",
            },
        )
        await session.commit()
    return capture_id, item_id


@pytest.mark.asyncio
async def test_repository_preserves_idempotency_user_scope_and_shared_item_relationships() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE preference_signals, look_components, looks, "
                "items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()

    user_id = uuid4()
    first_capture_id, shared_item_id = await insert_capture_and_item(
        sessions=sessions,
        user_id=user_id,
        suffix="a",
    )
    second_capture_id, _ = await insert_capture_and_item(
        sessions=sessions,
        user_id=user_id,
        suffix="b",
    )
    repository = SqlAlchemyLookRepository(sessions)

    first_candidate = Look.feed_saved(
        user_id=user_id,
        capture_id=first_capture_id,
        source_selection_key="whole-a",
    )
    first = await repository.ensure_placeholder(
        first_candidate,
        PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=first_candidate.id,
            idempotency_key="save-a",
        ),
    )
    duplicate_candidate = Look.feed_saved(
        user_id=user_id,
        capture_id=first_capture_id,
        source_selection_key="whole-a",
    )
    duplicate = await repository.ensure_placeholder(
        duplicate_candidate,
        PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=duplicate_candidate.id,
            idempotency_key="save-a",
        ),
    )
    second_candidate = Look.feed_saved(
        user_id=user_id,
        capture_id=second_capture_id,
        source_selection_key="whole-b",
    )
    second = await repository.ensure_placeholder(
        second_candidate,
        PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=second_candidate.id,
            idempotency_key="save-b",
        ),
    )
    evidence = (
        NormalizedPoint(0.1, 0.1),
        NormalizedPoint(0.8, 0.1),
        NormalizedPoint(0.8, 0.9),
    )
    await repository.save_component(
        LookComponent.pending(
            look_id=first.id,
            component_key="jacket",
            evidence_region=evidence,
            confidence=0.9,
            grounding_metadata={"schema_version": "grounding-v1"},
        ).with_item(shared_item_id)
    )
    await repository.save_component(
        LookComponent.pending(
            look_id=second.id,
            component_key="jacket",
            evidence_region=evidence,
            confidence=0.8,
            grounding_metadata={"schema_version": "grounding-v1"},
        ).with_item(shared_item_id)
    )
    reason = PreferenceSignal.liking_reason(
        user_id=user_id,
        look_id=first.id,
        reason="喜欢叠穿",
        idempotency_key="reason-a",
    )

    stored_reason = await repository.append_preference(reason)
    duplicate_reason = await repository.append_preference(reason)
    displayed = await repository.save(first.with_display_object("derived/looks/first.webp"))
    detail = await repository.get_detail_for_user(first.id, user_id)

    assert duplicate.id == first.id
    assert stored_reason == duplicate_reason
    assert displayed.display_object_key == "derived/looks/first.webp"
    assert detail is not None
    assert detail.look == displayed
    assert detail.components[0].item_id == shared_item_id
    assert len(detail.preference_signals) == 2
    assert {look.id for look in await repository.list_for_user(user_id)} == {
        first.id,
        second.id,
    }
    assert await repository.get_detail_for_user(first.id, uuid4()) is None

    async with sessions() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO look_components (
                        id, look_id, component_key, status, item_id,
                        evidence_region, display_order, confidence,
                        grounding_metadata, created_at, updated_at
                    ) VALUES (
                        :id, :look_id, 'fabricated-pending', 'pending', :item_id,
                        CAST(:evidence_region AS jsonb),
                        0, 0.5, '{}'::jsonb, now(), now()
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "look_id": first.id,
                    "item_id": shared_item_id,
                    "evidence_region": ('[{"x":0.1,"y":0.1},{"x":0.8,"y":0.1},{"x":0.8,"y":0.9}]'),
                },
            )
            await session.commit()

    deleted_first = await repository.delete_for_user(
        first.id,
        user_id,
        delete_items=True,
    )
    assert deleted_first is not None
    assert deleted_first.deleted_item_ids == ()
    assert deleted_first.preserved_shared_item_ids == (shared_item_id,)
    assert await repository.get_detail_for_user(first.id, user_id) is None

    deleted_second = await repository.delete_for_user(
        second.id,
        user_id,
        delete_items=True,
    )
    assert deleted_second is not None
    assert deleted_second.deleted_item_ids == (shared_item_id,)
    assert deleted_second.preserved_shared_item_ids == ()
    async with sessions() as session:
        assert (
            await session.execute(
                text("SELECT id FROM items WHERE id = :item_id"),
                {"item_id": shared_item_id},
            )
        ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_placeholder_save_key_reuse_cannot_represent_a_different_look() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE preference_signals, look_components, looks, "
                "items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()

    user_id = uuid4()
    first_capture_id, _ = await insert_capture_and_item(
        sessions=sessions,
        user_id=user_id,
        suffix="g",
    )
    second_capture_id, _ = await insert_capture_and_item(
        sessions=sessions,
        user_id=user_id,
        suffix="h",
    )
    repository = SqlAlchemyLookRepository(sessions)
    first_candidate = Look.feed_saved(
        user_id=user_id,
        capture_id=first_capture_id,
        source_selection_key="whole-g",
    )
    first_signal = PreferenceSignal.look_saved(
        user_id=user_id,
        look_id=first_candidate.id,
        idempotency_key="shared-save-key",
    )
    first = await repository.ensure_placeholder(first_candidate, first_signal)
    second_candidate = Look.feed_saved(
        user_id=user_id,
        capture_id=second_capture_id,
        source_selection_key="whole-h",
    )
    conflicting_signal = PreferenceSignal.look_saved(
        user_id=user_id,
        look_id=second_candidate.id,
        idempotency_key=first_signal.idempotency_key,
    )

    with pytest.raises(
        PreferenceIdempotencyConflict,
        match="preference idempotency conflict",
    ):
        await repository.ensure_placeholder(second_candidate, conflicting_signal)

    first_detail = await repository.get_detail_for_user(first.id, user_id)
    assert first_detail is not None
    assert len(first_detail.preference_signals) == 1
    assert first_detail.preference_signals[0].look_id == first.id
    assert first_detail.preference_signals[0].idempotency_key == "shared-save-key"


@pytest.mark.asyncio
async def test_ready_component_rejects_an_item_owned_by_another_user() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE preference_signals, look_components, looks, "
                "items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()

    owner_id = uuid4()
    capture_id, _ = await insert_capture_and_item(
        sessions=sessions,
        user_id=owner_id,
        suffix="c",
    )
    _, foreign_item_id = await insert_capture_and_item(
        sessions=sessions,
        user_id=uuid4(),
        suffix="d",
    )
    repository = SqlAlchemyLookRepository(sessions)
    candidate = Look.feed_saved(
        user_id=owner_id,
        capture_id=capture_id,
        source_selection_key="whole-c",
    )
    look = await repository.ensure_placeholder(
        candidate,
        PreferenceSignal.look_saved(
            user_id=owner_id,
            look_id=candidate.id,
            idempotency_key="save-c",
        ),
    )
    component = LookComponent.pending(
        look_id=look.id,
        component_key="foreign-jacket",
        evidence_region=(
            NormalizedPoint(0.1, 0.1),
            NormalizedPoint(0.8, 0.1),
            NormalizedPoint(0.8, 0.9),
        ),
        confidence=0.9,
        grounding_metadata={"schema_version": "grounding-v1"},
    ).with_item(foreign_item_id)

    with pytest.raises(ValueError, match="belongs to another user"):
        await repository.save_component(component)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conflict_field",
    ["look_id", "kind", "payload"],
)
async def test_preference_idempotency_rejects_different_semantics(
    conflict_field: str,
) -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE preference_signals, look_components, looks, "
                "items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()

    user_id = uuid4()
    first_capture_id, _ = await insert_capture_and_item(
        sessions=sessions,
        user_id=user_id,
        suffix="e",
    )
    second_capture_id, _ = await insert_capture_and_item(
        sessions=sessions,
        user_id=user_id,
        suffix="f",
    )
    repository = SqlAlchemyLookRepository(sessions)
    first_candidate = Look.feed_saved(
        user_id=user_id,
        capture_id=first_capture_id,
        source_selection_key="whole-e",
    )
    first = await repository.ensure_placeholder(
        first_candidate,
        PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=first_candidate.id,
            idempotency_key="save-e",
        ),
    )
    second_candidate = Look.feed_saved(
        user_id=user_id,
        capture_id=second_capture_id,
        source_selection_key="whole-f",
    )
    second = await repository.ensure_placeholder(
        second_candidate,
        PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=second_candidate.id,
            idempotency_key="save-f",
        ),
    )
    original = PreferenceSignal.liking_reason(
        user_id=user_id,
        look_id=first.id,
        reason="喜欢层次",
        idempotency_key="preference-conflict",
    )
    await repository.append_preference(original)
    if conflict_field == "look_id":
        conflicting = PreferenceSignal.liking_reason(
            user_id=user_id,
            look_id=second.id,
            reason="喜欢层次",
            idempotency_key=original.idempotency_key,
        )
    elif conflict_field == "kind":
        conflicting = PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=first.id,
            idempotency_key=original.idempotency_key,
        )
    else:
        conflicting = PreferenceSignal.liking_reason(
            user_id=user_id,
            look_id=first.id,
            reason="喜欢配色",
            idempotency_key=original.idempotency_key,
        )

    with pytest.raises(
        PreferenceIdempotencyConflict,
        match="preference idempotency conflict",
    ):
        await repository.append_preference(conflicting)


@pytest.mark.asyncio
async def test_save_reloads_the_canonical_id_after_identity_conflict() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE preference_signals, look_components, looks, "
                "items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()

    user_id = uuid4()
    capture_id, _ = await insert_capture_and_item(
        sessions=sessions,
        user_id=user_id,
        suffix="1",
    )
    repository = SqlAlchemyLookRepository(sessions)
    canonical_candidate = Look.feed_saved(
        user_id=user_id,
        capture_id=capture_id,
        source_selection_key="whole-1",
    )
    canonical = await repository.ensure_placeholder(
        canonical_candidate,
        PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=canonical_candidate.id,
            idempotency_key="save-1",
        ),
    )
    conflicting_candidate = Look.feed_saved(
        user_id=user_id,
        capture_id=capture_id,
        source_selection_key="whole-1",
    ).with_display_object("derived/looks/canonical.webp")

    saved = await repository.save(conflicting_candidate)

    assert conflicting_candidate.id != canonical.id
    assert saved.id == canonical.id
    assert saved.display_object_key == "derived/looks/canonical.webp"


@pytest.mark.asyncio
async def test_ai_composition_is_idempotent_without_a_fabricated_capture() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE preference_signals, look_components, looks, "
                "items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()

    user_id = uuid4()
    capture_id, item_id = await insert_capture_and_item(
        sessions=sessions,
        user_id=user_id,
        suffix="composition",
    )
    repository = SqlAlchemyLookRepository(sessions)
    proposed = Look.ai_generated(
        user_id=user_id,
        source_selection_key="aicomposition",
        analysis=composition_analysis(),
    )
    component = LookComponent.pending(
        look_id=proposed.id,
        component_key="slot1",
        evidence_region=(),
        confidence=0,
        grounding_metadata={
            "evidence_type": COMPOSITION_ITEM_EVIDENCE,
            "item_capture_id": str(capture_id),
            "item_selection_key": "item-composition",
            "item_version": "2026-07-26T00:00:00+00:00",
        },
    ).with_item(item_id)
    first = await repository.save_bundle(
        proposed,
        (component,),
        PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=proposed.id,
            idempotency_key="save-composition",
        ),
    )
    duplicate = Look.ai_generated(
        user_id=user_id,
        source_selection_key="aicomposition",
        analysis=composition_analysis(),
    )
    second = await repository.save_bundle(
        duplicate,
        (),
        PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=duplicate.id,
            idempotency_key="save-composition",
        ),
    )

    detail = await repository.get_detail_for_user(first.id, user_id)
    assert second.id == first.id
    assert first.capture_id is None
    assert detail is not None
    assert detail.components[0].item_id == item_id
    assert detail.components[0].evidence_region == ()
    assert detail.components[0].confidence == 0
