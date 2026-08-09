import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    FeedFrameContext,
    FeedSelection,
    NormalizedPoint,
    OwnershipState,
)
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitRecallRequirements,
)
from stylecapture_backend.features.wardrobe.domain import (
    FieldProvenance,
    ItemStatus,
    ModelField,
    WardrobeItem,
)
from stylecapture_backend.features.wardrobe.infrastructure.repository import (
    SqlAlchemyWardrobeRepository,
)
from stylecapture_backend.platform.database import build_session_factory, run_migrations

TEST_DATABASE_URL = os.environ.get(
    "STYLECAPTURE_TEST_DATABASE_URL",
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture_test",
)


@pytest.mark.asyncio
async def test_wardrobe_repository_round_trips_locked_fields_metadata_and_vector() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE items, processing_jobs, captures CASCADE"))
        capture = Capture.create(
            user_id=uuid4(),
            source=CaptureSource(
                kind=CaptureSourceKind.UPLOAD,
                object_key="originals/2026/07/25/wardrobe.png",
                sha256="f" * 64,
            ),
            ownership=OwnershipState.OWNED,
        )
        await session.execute(
            text(
                """
                INSERT INTO captures (
                    id, user_id, source_kind, object_key, sha256,
                    ownership, idempotency_key, created_at
                ) VALUES (
                    :id, :user_id, :source_kind, :object_key, :sha256,
                    :ownership, :idempotency_key, :created_at
                )
                """
            ),
            {
                "id": capture.id,
                "user_id": capture.user_id,
                "source_kind": capture.source.kind.value,
                "object_key": capture.source.object_key,
                "sha256": capture.source.sha256,
                "ownership": capture.ownership.value,
                "idempotency_key": "wardrobe-repo-001",
                "created_at": capture.created_at,
            },
        )
        await session.commit()

    repository = SqlAlchemyWardrobeRepository(sessions)
    item = WardrobeItem.processing(capture).correct("category", "outerwear")
    item = item.apply_model(
        {
            "category": ModelField("tops", 0.98, "vision-v1"),
            "description": ModelField("一件蓝色外套", 0.9, "vision-v1"),
        },
        {"capability_alias": "vision_understanding", "schema_version": "garment-v1"},
    )
    item = item.with_embedding(
        (1.0,) + (0.0,) * 2047,
        model_version="doubao-embedding-vision-250615",
    ).with_status(ItemStatus.READY)

    await repository.save(item)
    stored = await repository.get_by_capture(capture.id)
    listed = await repository.list_for_user(capture.user_id)
    recalled = await repository.recall_for_outfit(
        user_id=capture.user_id,
        requirements=OutfitRecallRequirements(
            scene="通勤",
            weather="温和",
            formality="日常得体",
            season="春季",
            exclude_item_ids=(),
            required_roles=(OutfitCategory.OUTERWEAR,),
            anchor_item_id=item.id,
        ),
    )
    owner_scoped = await repository.get_for_user(item.id, capture.user_id)

    assert stored is not None
    assert stored == item
    assert listed == [item]
    assert recalled == [item]
    assert owner_scoped == item
    assert await repository.get_for_user(item.id, uuid4()) is None
    assert stored.attributes.fields["category"].value == "outerwear"
    assert stored.attributes.fields["category"].provenance is FieldProvenance.USER
    assert stored.attributes.fields["description"].value == "一件蓝色外套"
    assert stored.model_metadata["embedding_model"] == "doubao-embedding-vision-250615"
    assert stored.embedding == (1.0,) + (0.0,) * 2047

    assert await repository.delete_for_user(item.id, uuid4()) is False
    assert await repository.delete_for_user(item.id, capture.user_id) is True
    assert await repository.get_for_user(item.id, capture.user_id) is None


@pytest.mark.asyncio
async def test_outfit_recall_filters_assets_and_stably_ranks_owned_vectors() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    user_id = uuid4()
    captures = [
        Capture.create(
            user_id=user_id,
            source=CaptureSource(
                kind=CaptureSourceKind.UPLOAD,
                object_key=f"originals/2026/07/26/recall-{index}.png",
                sha256=f"{index:x}" * 64,
            ),
            ownership=ownership,
        )
        for index, ownership in enumerate(
            (
                OwnershipState.OWNED,
                OwnershipState.OWNED,
                OwnershipState.OWNED,
                OwnershipState.INSPIRATION,
                OwnershipState.OWNED,
                OwnershipState.OWNED,
                OwnershipState.OWNED,
            ),
            start=1,
        )
    ]
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE items, processing_jobs, captures CASCADE"))
        await session.execute(
            text(
                """
                INSERT INTO captures (
                    id, user_id, source_kind, object_key, sha256,
                    ownership, idempotency_key, created_at
                ) VALUES (
                    :id, :user_id, :source_kind, :object_key, :sha256,
                    :ownership, :idempotency_key, :created_at
                )
                """
            ),
            [
                {
                    "id": capture.id,
                    "user_id": capture.user_id,
                    "source_kind": capture.source.kind.value,
                    "object_key": capture.source.object_key,
                    "sha256": capture.source.sha256,
                    "ownership": capture.ownership.value,
                    "idempotency_key": f"outfit-recall-{index}",
                    "created_at": capture.created_at,
                }
                for index, capture in enumerate(captures, start=1)
            ],
        )
        await session.commit()

    def ready_item(
        capture: Capture,
        *,
        category: str,
        vector: tuple[float, ...],
        status: ItemStatus = ItemStatus.READY,
    ) -> WardrobeItem:
        return (
            WardrobeItem.processing(capture)
            .correct("category", category)
            .with_embedding(vector, model_version="test-vector-v1")
            .with_status(status)
        )

    anchor = ready_item(
        captures[0],
        category="tops",
        vector=(1.0,) + (0.0,) * 2047,
    )
    near = ready_item(
        captures[1],
        category="tops",
        vector=(0.9938837347, 0.1104315261) + (0.0,) * 2046,
        status=ItemStatus.PARTIAL,
    )
    far = ready_item(
        captures[2],
        category="tops",
        vector=(0.0, 1.0) + (0.0,) * 2046,
    )
    inspiration = ready_item(
        captures[3],
        category="tops",
        vector=(1.0,) + (0.0,) * 2047,
    )
    excluded = ready_item(
        captures[4],
        category="tops",
        vector=(1.0,) + (0.0,) * 2047,
    )
    wrong_category = ready_item(
        captures[5],
        category="bottoms",
        vector=(1.0,) + (0.0,) * 2047,
    )
    errored = ready_item(
        captures[6],
        category="tops",
        vector=(1.0,) + (0.0,) * 2047,
        status=ItemStatus.ERROR,
    )
    repository = SqlAlchemyWardrobeRepository(sessions)
    for item in (
        anchor,
        near,
        far,
        inspiration,
        excluded,
        wrong_category,
        errored,
    ):
        await repository.save(item)

    recalled = await repository.recall_for_outfit(
        user_id=user_id,
        requirements=OutfitRecallRequirements(
            scene="客户提案",
            weather="温和",
            formality="正式",
            season="春季",
            exclude_item_ids=(excluded.id,),
            required_roles=(OutfitCategory.TOP,),
            anchor_item_id=anchor.id,
        ),
    )

    assert [item.id for item in recalled] == [
        anchor.id,
        near.id,
        far.id,
        inspiration.id,
    ]
    assert all(item.attributes.fields["category"].value == "tops" for item in recalled)
    assert all(item.status in {ItemStatus.READY, ItemStatus.PARTIAL} for item in recalled)


@pytest.mark.asyncio
async def test_worker_save_cannot_resurrect_deleted_source_or_overwrite_user_truth() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    user_id = uuid4()
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.UPLOAD,
            object_key="originals/2026/07/25/concurrent.png",
            sha256="e" * 64,
        ),
        ownership=OwnershipState.OWNED,
    )
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE items, processing_jobs, captures CASCADE"))
        await session.execute(
            text(
                """
                INSERT INTO captures (
                    id, user_id, source_kind, object_key, sha256,
                    ownership, idempotency_key, created_at
                ) VALUES (
                    :id, :user_id, :source_kind, :object_key, :sha256,
                    :ownership, :idempotency_key, :created_at
                )
                """
            ),
            {
                "id": capture.id,
                "user_id": capture.user_id,
                "source_kind": capture.source.kind.value,
                "object_key": capture.source.object_key,
                "sha256": capture.source.sha256,
                "ownership": capture.ownership.value,
                "idempotency_key": "wardrobe-concurrency-001",
                "created_at": capture.created_at,
            },
        )
        await session.commit()

    repository = SqlAlchemyWardrobeRepository(sessions)
    stale_worker_item = await repository.save(WardrobeItem.processing(capture))
    user_item = (
        stale_worker_item.correct("category", "outerwear")
        .with_ownership(OwnershipState.INSPIRATION)
        .with_source_deleted()
    )
    await repository.save_user_state(user_item)

    await repository.save(stale_worker_item.with_status(ItemStatus.ERROR))
    stored = await repository.get_by_capture(capture.id)

    assert stored is not None
    assert stored.status is ItemStatus.ERROR
    assert stored.source_available is False
    assert stored.ownership is OwnershipState.INSPIRATION
    assert stored.attributes.fields["category"].value == "outerwear"
    assert stored.attributes.fields["category"].locked is True


@pytest.mark.asyncio
async def test_repository_persists_multiple_feed_items_by_stable_selection_key() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    user_id = uuid4()
    polygon = (
        NormalizedPoint(0.1, 0.1),
        NormalizedPoint(0.4, 0.1),
        NormalizedPoint(0.4, 0.5),
        NormalizedPoint(0.1, 0.5),
    )
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.FEED,
            object_key="originals/2026/07/25/two-selections.png",
            sha256="d" * 64,
        ),
        ownership=OwnershipState.INSPIRATION,
        feed_context=FeedFrameContext(
            video_ref="pexels-123",
            timestamp_ms=1_000,
            frame_width=720,
            frame_height=1280,
            selections=(
                FeedSelection(selection_key="hat", polygon=polygon),
                FeedSelection(selection_key="jacket", polygon=polygon),
            ),
        ),
    )
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE items, processing_jobs, captures CASCADE"))
        await session.execute(
            text(
                """
                INSERT INTO captures (
                    id, user_id, source_kind, object_key, sha256,
                    ownership, idempotency_key, created_at
                ) VALUES (
                    :id, :user_id, :source_kind, :object_key, :sha256,
                    :ownership, :idempotency_key, :created_at
                )
                """
            ),
            {
                "id": capture.id,
                "user_id": capture.user_id,
                "source_kind": capture.source.kind.value,
                "object_key": capture.source.object_key,
                "sha256": capture.source.sha256,
                "ownership": capture.ownership.value,
                "idempotency_key": "wardrobe-two-selections-001",
                "created_at": capture.created_at,
            },
        )
        await session.commit()

    repository = SqlAlchemyWardrobeRepository(sessions)
    hat = await repository.save(WardrobeItem.processing(capture, selection_key="hat"))
    jacket = await repository.save(WardrobeItem.processing(capture, selection_key="jacket"))
    duplicate_hat = await repository.save(WardrobeItem.processing(capture, selection_key="hat"))

    assert hat.id != jacket.id
    assert duplicate_hat.id == hat.id
    assert await repository.get_by_capture(capture.id, "hat") == duplicate_hat
    assert await repository.get_by_capture(capture.id, "jacket") == jacket
    assert {item.selection_key for item in await repository.list_for_user(user_id)} == {
        "hat",
        "jacket",
    }

    await repository.save_user_state(duplicate_hat.with_source_deleted())

    stored_hat = await repository.get_by_capture(capture.id, "hat")
    stored_jacket = await repository.get_by_capture(capture.id, "jacket")
    assert stored_hat is not None
    assert stored_jacket is not None
    assert stored_hat.source_available is False
    assert stored_jacket.source_available is False


@pytest.mark.asyncio
async def test_existing_whole_capture_item_keeps_default_selection_identity() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    user_id = uuid4()
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.CAMERA,
            object_key="originals/2026/07/25/legacy-camera.png",
            sha256="c" * 64,
        ),
        ownership=OwnershipState.OWNED,
    )
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE items, processing_jobs, captures CASCADE"))
        await session.execute(
            text(
                """
                INSERT INTO captures (
                    id, user_id, source_kind, object_key, sha256,
                    ownership, idempotency_key, created_at
                ) VALUES (
                    :id, :user_id, :source_kind, :object_key, :sha256,
                    :ownership, :idempotency_key, :created_at
                )
                """
            ),
            {
                "id": capture.id,
                "user_id": capture.user_id,
                "source_kind": capture.source.kind.value,
                "object_key": capture.source.object_key,
                "sha256": capture.source.sha256,
                "ownership": capture.ownership.value,
                "idempotency_key": "wardrobe-legacy-default-001",
                "created_at": capture.created_at,
            },
        )
        await session.commit()

    repository = SqlAlchemyWardrobeRepository(sessions)
    saved = await repository.save(WardrobeItem.processing(capture))

    assert saved.selection_key == "whole_capture"
    assert await repository.get_by_capture(capture.id) == saved
