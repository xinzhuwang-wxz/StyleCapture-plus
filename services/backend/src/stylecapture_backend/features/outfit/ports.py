from __future__ import annotations

from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.outfit.domain import (
    OutfitPlan,
    OutfitRequest,
)
from stylecapture_backend.features.wardrobe.domain import WardrobeItem


class OutfitWardrobeReader(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[WardrobeItem]: ...


class OutfitReranker(Protocol):
    async def rerank(
        self,
        request: OutfitRequest,
        plans: tuple[OutfitPlan, ...],
    ) -> tuple[OutfitPlan, ...]: ...
