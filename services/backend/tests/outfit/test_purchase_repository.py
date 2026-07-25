from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from stylecapture_backend.features.capture.domain import OwnershipState
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitSlot,
    PurchaseDemandStatus,
)
from stylecapture_backend.features.outfit.infrastructure.repository import (
    SqlAlchemyPurchaseDemandRepository,
)
from stylecapture_backend.features.outfit.ports import OutfitPostSaveUnavailable
from stylecapture_backend.features.wardrobe.infrastructure.repository import (
    SqlAlchemyWardrobeRepository,
)
from stylecapture_backend.platform.database import build_session_factory, run_migrations

TEST_DATABASE_URL = os.environ.get(
    "STYLECAPTURE_TEST_DATABASE_URL",
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture_test",
)


@pytest.mark.asyncio
async def test_operational_error_is_translated_to_retryable_post_save_failure() -> None:
    def broken_sessions() -> AsyncSession:
        raise OperationalError(
            "connect",
            {},
            ConnectionError("database temporarily unavailable"),
        )

    repository = SqlAlchemyPurchaseDemandRepository(
        cast(
            async_sessionmaker[AsyncSession],
            cast(Callable[[], AsyncSession], broken_sessions),
        )
    )
    look_id = uuid4()
    user_id = uuid4()
    plan = OutfitPlan(
        id=uuid4(),
        title="通勤补齐",
        scene="上班",
        slots=(
            OutfitSlot(
                role=OutfitCategory.TOP,
                item_id=None,
                item_name=None,
                ownership=None,
                image_url=None,
                search_query="白色衬衫",
                source_kind=None,
            ),
            OutfitSlot(
                role=OutfitCategory.BOTTOM,
                item_id=None,
                item_name=None,
                ownership=None,
                image_url=None,
                search_query="黑色西裤",
                source_kind=None,
            ),
            OutfitSlot(
                role=OutfitCategory.SHOES,
                item_id=None,
                item_name=None,
                ownership=None,
                image_url=None,
                search_query="黑色乐福鞋",
                source_kind=None,
            ),
        ),
        rationale="需要补齐鞋履。",
        style_match_score=80,
    )

    with pytest.raises(OutfitPostSaveUnavailable):
        await repository.ensure_for_plan(
            user_id=user_id,
            look_id=look_id,
            plan=plan,
        )


@pytest.mark.asyncio
async def test_receiving_linked_inspiration_updates_the_real_item_atomically() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    wardrobe = SqlAlchemyWardrobeRepository(sessions)
    repository = SqlAlchemyPurchaseDemandRepository(
        sessions,
        wardrobe=wardrobe,
    )
    user_id = uuid4()
    capture_id = uuid4()
    item_id = uuid4()
    look_id = uuid4()
    now = datetime.now(UTC)

    async with sessions() as session:
        await session.execute(
            text("TRUNCATE TABLE outfit_purchase_demands, looks, items, captures CASCADE")
        )
        await session.execute(
            text(
                """
                INSERT INTO captures (
                    id, user_id, source_kind, object_key, sha256,
                    ownership, idempotency_key, created_at
                ) VALUES (
                    :capture_id, :user_id, 'upload', 'originals/inspiration.png',
                    :sha256, 'inspiration', 'purchase-link-capture', :now
                )
                """
            ),
            {
                "capture_id": capture_id,
                "user_id": user_id,
                "sha256": "a" * 64,
                "now": now,
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
                    :item_id, :user_id, :capture_id, 'whole_capture',
                    'originals/inspiration.png', NULL, TRUE, 'inspiration', 'ready',
                    CAST(:attributes AS jsonb), CAST(:metadata AS jsonb), :now, :now
                )
                """
            ),
            {
                "item_id": item_id,
                "user_id": user_id,
                "capture_id": capture_id,
                "attributes": (
                    '{"category":{"value":"tops","provenance":"curated_seed",'
                    '"confidence":1,"model_version":null,"locked":false}}'
                ),
                "metadata": "{}",
                "now": now,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO looks (
                    id, user_id, capture_id, source_selection_key, source,
                    status, analysis, display_object_key, created_at, updated_at
                ) VALUES (
                    :look_id, :user_id, :capture_id, 'purchase_plan',
                    'feed_saved', 'ready', NULL, NULL, :now, :now
                )
                """
            ),
            {
                "look_id": look_id,
                "user_id": user_id,
                "capture_id": capture_id,
                "now": now,
            },
        )
        await session.commit()

    plan = OutfitPlan(
        id=uuid4(),
        title="真实购买状态",
        scene="通勤",
        slots=(
            OutfitSlot(
                role=OutfitCategory.TOP,
                item_id=item_id,
                item_name="米白针织上衣",
                ownership="inspiration",
                image_url=f"/v1/items/{item_id}/image",
                search_query=None,
                source_kind="upload",
            ),
            OutfitSlot(
                role=OutfitCategory.BOTTOM,
                item_id=None,
                item_name=None,
                ownership=None,
                image_url=None,
                search_query="黑色西裤",
            ),
            OutfitSlot(
                role=OutfitCategory.SHOES,
                item_id=None,
                item_name=None,
                ownership=None,
                image_url=None,
                search_query="黑色乐福鞋",
            ),
        ),
        rationale="一件灵感单品和两件待补齐商品。",
        style_match_score=88,
    )
    demands = await repository.ensure_for_plan(
        user_id=user_id,
        look_id=look_id,
        plan=plan,
    )
    linked = next(demand for demand in demands if demand.item_id == item_id)
    unlinked = next(demand for demand in demands if demand.item_id is None)

    linked = await repository.advance(
        user_id=user_id,
        demand_id=linked.id,
        target=PurchaseDemandStatus.PURCHASED_PENDING,
    )
    linked = await repository.advance(
        user_id=user_id,
        demand_id=linked.id,
        target=PurchaseDemandStatus.OWNED,
    )
    stored_item = await wardrobe.get_for_user(item_id, user_id)

    assert linked.status is PurchaseDemandStatus.OWNED
    assert linked.can_mark_owned is True
    assert stored_item is not None
    assert stored_item.ownership is OwnershipState.OWNED

    unlinked = await repository.advance(
        user_id=user_id,
        demand_id=unlinked.id,
        target=PurchaseDemandStatus.PURCHASED_PENDING,
    )
    with pytest.raises(ValueError, match="linked wardrobe item"):
        await repository.advance(
            user_id=user_id,
            demand_id=unlinked.id,
            target=PurchaseDemandStatus.OWNED,
        )
    unchanged = await repository.get_for_user(
        user_id=user_id,
        demand_id=unlinked.id,
    )
    assert unchanged is not None
    assert unchanged.status is PurchaseDemandStatus.PURCHASED_PENDING
