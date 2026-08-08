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
    DefaultItemFlatLayScheduler,
)


class RecordingPresentations:
    def __init__(self, view: ItemPresentationView) -> None:
        self.view = view
        self.requested: tuple[UUID, UUID] | None = None

    async def ensure_flat_lay_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
    ) -> ItemPresentationView:
        self.requested = (user_id, item_id)
        return self.view

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
        self.enqueued: tuple[UUID, UUID] | None = None

    def enqueue_item_presentation(self, *, user_id: UUID, asset_id: UUID) -> None:
        self.enqueued = (user_id, asset_id)


@pytest.mark.asyncio
async def test_new_ready_item_queues_its_flat_lay_presentation() -> None:
    user_id = uuid4()
    item_id = uuid4()
    asset_id = uuid4()
    now = datetime.now(UTC)
    view = ItemPresentationView(
        id=asset_id,
        user_id=user_id,
        item_id=item_id,
        kind=ItemPresentationKind.FLAT_LAY_ITEM,
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
    presentations = RecordingPresentations(view)
    dispatcher = RecordingDispatcher()
    scheduler = DefaultItemFlatLayScheduler(
        presentations=presentations,
        dispatcher=dispatcher,
    )

    await scheduler.enqueue_for_item(user_id=user_id, item_id=item_id)

    assert presentations.requested == (user_id, item_id)
    assert dispatcher.enqueued == (user_id, asset_id)
