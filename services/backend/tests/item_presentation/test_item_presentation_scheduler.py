from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.item_presentation.application import ItemPresentationView
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationKind,
    ItemPresentationStatus,
)
from stylecapture_backend.features.item_presentation.infrastructure.scheduler import (
    DefaultItemPresentationScheduler,
)


class RecordingPresentations:
    def __init__(self, views: dict[ItemPresentationKind, ItemPresentationView]) -> None:
        self.views = views
        self.requested: list[tuple[ItemPresentationKind, UUID, UUID]] = []

    async def ensure_pixel_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
    ) -> ItemPresentationView:
        self.requested.append((ItemPresentationKind.PIXEL_ITEM, user_id, item_id))
        return self.views[ItemPresentationKind.PIXEL_ITEM]

    async def ensure_flat_lay_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
    ) -> ItemPresentationView:
        self.requested.append((ItemPresentationKind.FLAT_LAY_ITEM, user_id, item_id))
        return self.views[ItemPresentationKind.FLAT_LAY_ITEM]

    async def mark_failed(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        code: str,
        message: str,
    ) -> ItemPresentationView:
        raise AssertionError("dispatch succeeds in this test")


class RecordingDispatcher:
    def __init__(self) -> None:
        self.enqueued: list[tuple[UUID, UUID]] = []

    def enqueue_item_presentation(self, *, user_id: UUID, asset_id: UUID) -> None:
        self.enqueued.append((user_id, asset_id))


@pytest.mark.asyncio
async def test_new_ready_item_queues_pixel_card_and_flat_lay_presentations() -> None:
    user_id = uuid4()
    item_id = uuid4()
    pixel_asset_id = uuid4()
    flat_lay_asset_id = uuid4()
    now = datetime.now(UTC)
    views = {
        kind: ItemPresentationView(
            id=asset_id,
            user_id=user_id,
            item_id=item_id,
            kind=kind,
            status=ItemPresentationStatus.QUEUED,
            object_key=None,
            content_hash=None,
            content_type=None,
            failure_code=None,
            failure_message=None,
            created_at=now,
            updated_at=now,
            dispatch_required=True,
        )
        for kind, asset_id in (
            (ItemPresentationKind.PIXEL_ITEM, pixel_asset_id),
            (ItemPresentationKind.FLAT_LAY_ITEM, flat_lay_asset_id),
        )
    }
    presentations = RecordingPresentations(views)
    dispatcher = RecordingDispatcher()
    scheduler = DefaultItemPresentationScheduler(
        presentations=presentations,
        dispatcher=dispatcher,
    )

    await scheduler.enqueue_for_item(user_id=user_id, item_id=item_id)

    assert presentations.requested == [
        (ItemPresentationKind.PIXEL_ITEM, user_id, item_id),
        (ItemPresentationKind.FLAT_LAY_ITEM, user_id, item_id),
    ]
    assert dispatcher.enqueued == [
        (user_id, pixel_asset_id),
        (user_id, flat_lay_asset_id),
    ]
