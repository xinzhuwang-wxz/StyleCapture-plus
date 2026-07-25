from __future__ import annotations

from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationAsset,
    ItemPresentationKind,
)
from stylecapture_backend.features.render.domain import RenderInputSignature
from stylecapture_backend.features.wardrobe.domain import WardrobeItem

ITEM_PRESENTATION_TASK_NAME = "stylecapture.item_presentation.process"


class ItemPresentationNotFound(LookupError):
    """The requested item presentation asset is not visible to the current user."""


class ItemPresentationIdempotencyConflict(ValueError):
    """An item presentation request key was reused for different input."""


class ItemPresentationPersistenceUnavailable(RuntimeError):
    """The item presentation store is temporarily unavailable for a safe retry."""


class ItemPresentationDispatchError(RuntimeError):
    """The durable request exists, but the broker did not accept its task."""


class WardrobeItemReader(Protocol):
    async def get_item(self, user_id: UUID, item_id: UUID) -> WardrobeItem: ...


class ItemPresentationRepository(Protocol):
    async def ensure_requested(self, asset: ItemPresentationAsset) -> ItemPresentationAsset: ...

    async def save(self, asset: ItemPresentationAsset) -> ItemPresentationAsset: ...

    async def find_current(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        kind: ItemPresentationKind,
        input_signature: RenderInputSignature,
    ) -> ItemPresentationAsset | None: ...

    async def get_for_user(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
    ) -> ItemPresentationAsset | None: ...
