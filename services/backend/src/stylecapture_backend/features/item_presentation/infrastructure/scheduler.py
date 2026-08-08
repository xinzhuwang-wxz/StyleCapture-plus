from __future__ import annotations

from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.item_presentation.application import ItemPresentationView
from stylecapture_backend.features.item_presentation.domain import ItemPresentationStatus
from stylecapture_backend.features.item_presentation.ports import ItemPresentationDispatchError


class ItemPresentationDispatcher(Protocol):
    def enqueue_item_presentation(self, *, user_id: UUID, asset_id: UUID) -> None: ...


class ItemPresentationService(Protocol):
    async def ensure_flat_lay_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
    ) -> ItemPresentationView: ...

    async def mark_failed(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        code: str,
        message: str,
    ) -> ItemPresentationView: ...


class DefaultItemFlatLayScheduler:
    """Queue a generated item hero only for items completed by the capture worker."""

    def __init__(
        self,
        *,
        presentations: ItemPresentationService,
        dispatcher: ItemPresentationDispatcher,
    ) -> None:
        self._presentations = presentations
        self._dispatcher = dispatcher

    async def enqueue_for_item(self, *, user_id: UUID, item_id: UUID) -> None:
        view = await self._presentations.ensure_flat_lay_item(
            user_id=user_id,
            item_id=item_id,
        )
        if not view.dispatch_required or view.status is not ItemPresentationStatus.QUEUED:
            return
        try:
            self._dispatcher.enqueue_item_presentation(
                user_id=view.user_id,
                asset_id=view.id,
            )
        except ItemPresentationDispatchError:
            await self._presentations.mark_failed(
                user_id=view.user_id,
                asset_id=view.id,
                code="dispatch_unavailable",
                message="白底单品图任务暂时未启动, 原图和单品数据已正常保存",
            )
