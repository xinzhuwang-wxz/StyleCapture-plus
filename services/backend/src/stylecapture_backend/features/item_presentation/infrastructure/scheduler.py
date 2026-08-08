from __future__ import annotations

from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.item_presentation.application import ItemPresentationView
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationKind,
    ItemPresentationStatus,
)
from stylecapture_backend.features.item_presentation.ports import ItemPresentationDispatchError


class ItemPresentationDispatcher(Protocol):
    def enqueue_item_presentation(self, *, user_id: UUID, asset_id: UUID) -> None: ...


class ItemPresentationService(Protocol):
    async def ensure_pixel_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
    ) -> ItemPresentationView: ...

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


class DefaultItemPresentationScheduler:
    """Queue both Item-detail and wardrobe-card assets for newly completed Items."""

    def __init__(
        self,
        *,
        presentations: ItemPresentationService,
        dispatcher: ItemPresentationDispatcher,
    ) -> None:
        self._presentations = presentations
        self._dispatcher = dispatcher

    async def enqueue_for_item(self, *, user_id: UUID, item_id: UUID) -> None:
        views = (
            await self._presentations.ensure_pixel_item(user_id=user_id, item_id=item_id),
            await self._presentations.ensure_flat_lay_item(user_id=user_id, item_id=item_id),
        )
        for view in views:
            await self._dispatch(view)

    async def _dispatch(self, view: ItemPresentationView) -> None:
        if not view.dispatch_required or view.status is not ItemPresentationStatus.QUEUED:
            return
        try:
            self._dispatcher.enqueue_item_presentation(
                user_id=view.user_id,
                asset_id=view.id,
            )
        except ItemPresentationDispatchError:
            message = (
                "像素卡片任务暂时未启动, 单品已正常保存并可稍后重试"
                if view.kind is ItemPresentationKind.PIXEL_ITEM
                else "白底单品图任务暂时未启动, 原图和单品数据已正常保存"
            )
            await self._presentations.mark_failed(
                user_id=view.user_id,
                asset_id=view.id,
                code="dispatch_unavailable",
                message=message,
            )


# Compatibility alias for integrations that imported the first scheduler name.
DefaultItemFlatLayScheduler = DefaultItemPresentationScheduler
