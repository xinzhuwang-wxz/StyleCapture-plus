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
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture",
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
        (1.0,) + (0.0,) * 767,
        model_version="Marqo/marqo-fashionSigLIP@c56244c",
    ).with_status(ItemStatus.READY)

    await repository.save(item)
    stored = await repository.get_by_capture(capture.id)
    listed = await repository.list_for_user(capture.user_id)
    owner_scoped = await repository.get_for_user(item.id, capture.user_id)

    assert stored is not None
    assert stored == item
    assert listed == [item]
    assert owner_scoped == item
    assert await repository.get_for_user(item.id, uuid4()) is None
    assert stored.attributes.fields["category"].value == "outerwear"
    assert stored.attributes.fields["category"].provenance is FieldProvenance.USER
    assert stored.attributes.fields["description"].value == "一件蓝色外套"
    assert str(stored.model_metadata["embedding_model"]).startswith("Marqo/")
    assert stored.embedding == (1.0,) + (0.0,) * 767


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
    jacket = await repository.save(
        WardrobeItem.processing(capture, selection_key="jacket")
    )
    duplicate_hat = await repository.save(
        WardrobeItem.processing(capture, selection_key="hat")
    )

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
