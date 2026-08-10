import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationAsset,
    ItemPresentationKind,
)
from stylecapture_backend.features.item_presentation.infrastructure.models import (
    ItemPresentationAssetRecord,
)
from stylecapture_backend.features.item_presentation.infrastructure.repository import (
    SqlAlchemyItemPresentationRepository,
)
from stylecapture_backend.features.item_presentation.ports import (
    ItemPresentationIdempotencyConflict,
)
from stylecapture_backend.features.render.domain import RenderInputSignature, RenderOutput
from stylecapture_backend.platform.database import build_session_factory, run_migrations

TEST_DATABASE_URL = os.environ.get(
    "STYLECAPTURE_TEST_DATABASE_URL",
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture_test",
)


async def _insert_item(*, user_id: UUID, suffix: str) -> UUID:
    sessions = build_session_factory(TEST_DATABASE_URL)
    capture_id = uuid4()
    item_id = uuid4()
    now = datetime.now(UTC)
    async with sessions() as session:
        await session.execute(
            text(
                """
                INSERT INTO captures (
                    id, user_id, source_kind, object_key, sha256,
                    ownership, idempotency_key, created_at
                ) VALUES (
                    :capture_id, :user_id, 'upload', :object_key, :sha256,
                    'owned', :capture_key, :created_at
                )
                """
            ),
            {
                "capture_id": capture_id,
                "user_id": user_id,
                "object_key": f"originals/item-presentation-{suffix}.png",
                "sha256": suffix[0] * 64,
                "capture_key": f"item-presentation-{suffix}",
                "created_at": now,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO items (
                    id, user_id, capture_id, selection_key, source_object_key,
                    display_object_key, source_available, ownership, status,
                    attributes, model_metadata, created_at, updated_at
                ) VALUES (
                    :item_id, :user_id, :capture_id, 'whole_capture', :object_key,
                    :object_key, true, 'owned', 'ready',
                    '{}'::jsonb, '{}'::jsonb, :created_at, :created_at
                )
                """
            ),
            {
                "capture_id": capture_id,
                "item_id": item_id,
                "user_id": user_id,
                "object_key": f"originals/item-presentation-{suffix}.png",
                "created_at": now,
            },
        )
        await session.commit()
    return item_id


async def _reset_database() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE item_presentation_assets, items, processing_jobs, captures CASCADE"
            )
        )
        await session.commit()


def _queued(
    *,
    user_id: UUID,
    item_id: UUID,
    request_key: str,
    signature_hash: str = "a" * 64,
) -> ItemPresentationAsset:
    return ItemPresentationAsset.queued(
        user_id=user_id,
        item_id=item_id,
        kind=ItemPresentationKind.PIXEL_ITEM,
        input_signature=RenderInputSignature(
            version="item-pixel-v2",
            hash=signature_hash,
        ),
        request_key=request_key,
    )


@pytest.mark.asyncio
async def test_equivalent_signature_with_new_request_key_reuses_current_asset() -> None:
    await _reset_database()
    user_id = uuid4()
    item_id = await _insert_item(user_id=user_id, suffix="a")
    sessions = build_session_factory(TEST_DATABASE_URL)
    repository = SqlAlchemyItemPresentationRepository(sessions)

    first = await repository.ensure_requested(
        _queued(user_id=user_id, item_id=item_id, request_key="normal-pixel-request")
    )
    equivalent = await repository.ensure_requested(
        _queued(user_id=user_id, item_id=item_id, request_key="curated-seed-request")
    )

    async with sessions() as session:
        count = await session.scalar(select(func.count(ItemPresentationAssetRecord.id)))
    assert equivalent.id == first.id
    assert count == 1


@pytest.mark.asyncio
async def test_concurrent_equivalent_requests_share_one_current_asset() -> None:
    await _reset_database()
    user_id = uuid4()
    item_id = await _insert_item(user_id=user_id, suffix="b")
    sessions = build_session_factory(TEST_DATABASE_URL)
    repository = SqlAlchemyItemPresentationRepository(sessions)

    first, second = await asyncio.gather(
        repository.ensure_requested(
            _queued(user_id=user_id, item_id=item_id, request_key="pixel-concurrent-a")
        ),
        repository.ensure_requested(
            _queued(user_id=user_id, item_id=item_id, request_key="pixel-concurrent-b")
        ),
    )

    async with sessions() as session:
        count = await session.scalar(select(func.count(ItemPresentationAssetRecord.id)))
    assert first.id == second.id
    assert count == 1


@pytest.mark.asyncio
async def test_request_key_reuse_with_different_signature_is_rejected() -> None:
    await _reset_database()
    user_id = uuid4()
    item_id = await _insert_item(user_id=user_id, suffix="c")
    sessions = build_session_factory(TEST_DATABASE_URL)
    repository = SqlAlchemyItemPresentationRepository(sessions)
    await repository.ensure_requested(
        _queued(user_id=user_id, item_id=item_id, request_key="shared-request")
    )

    with pytest.raises(ItemPresentationIdempotencyConflict):
        await repository.ensure_requested(
            _queued(
                user_id=user_id,
                item_id=item_id,
                request_key="shared-request",
                signature_hash="d" * 64,
            )
        )


@pytest.mark.asyncio
async def test_save_allows_manual_retry_of_succeeded_asset() -> None:
    await _reset_database()
    user_id = uuid4()
    item_id = await _insert_item(user_id=user_id, suffix="d")
    sessions = build_session_factory(TEST_DATABASE_URL)
    repository = SqlAlchemyItemPresentationRepository(sessions)

    requested = await repository.ensure_requested(
        _queued(user_id=user_id, item_id=item_id, request_key="pixel-retry-after-success")
    )
    succeeded = await repository.save(
        requested.mark_succeeded(
            output=RenderOutput(
                object_key="derived/items/pixel/succeeded.png",
                content_hash="e" * 64,
                content_type="image/png",
            ),
            provider_trace=None,
        )
    )

    retried = await repository.save(succeeded.retry())

    assert retried.id == requested.id
    assert retried.status.value == "queued"
    assert retried.output is None
