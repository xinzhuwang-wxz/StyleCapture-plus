from __future__ import annotations

from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.outfit.domain import (
    OutfitPlan,
    OutfitReasoningTrace,
    OutfitRecallRequirements,
    OutfitRequest,
    OutfitRerankResult,
    OutfitWorkflowTrace,
    PurchaseDemand,
    PurchaseDemandStatus,
)
from stylecapture_backend.features.wardrobe.domain import WardrobeItem


class OutfitPostSaveUnavailable(RuntimeError):
    """A retryable dependency failed after the saved Look became durable."""


class OutfitWardrobeReader(Protocol):
    async def recall_for_outfit(
        self,
        *,
        user_id: UUID,
        requirements: OutfitRecallRequirements,
    ) -> list[WardrobeItem]: ...

    async def get_for_user(
        self,
        item_id: UUID,
        user_id: UUID,
    ) -> WardrobeItem | None: ...


class OutfitReranker(Protocol):
    async def rerank(
        self,
        request: OutfitRequest,
        plans: tuple[OutfitPlan, ...],
    ) -> OutfitRerankResult: ...


class OutfitPlanTickets(Protocol):
    def issue(
        self,
        *,
        user_id: UUID,
        plan: OutfitPlan,
        explanation_state: str,
        request: OutfitRequest,
        reasoning_trace: OutfitReasoningTrace | None = None,
    ) -> str: ...

    def verify(
        self,
        token: str,
        *,
        user_id: UUID,
        expected_plan_id: UUID,
    ) -> tuple[OutfitPlan, str, OutfitRequest, OutfitReasoningTrace | None]: ...


class OutfitWorkflowTraceRepository(Protocol):
    async def save(self, trace: OutfitWorkflowTrace) -> OutfitWorkflowTrace: ...

    async def get_for_user(
        self,
        *,
        trace_id: UUID,
        user_id: UUID,
    ) -> OutfitWorkflowTrace | None: ...


class OutfitPresentationScheduler(Protocol):
    async def enqueue_default_presentation(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
    ) -> None: ...


class PurchaseDemandRepository(Protocol):
    async def ensure_for_plan(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
        plan: OutfitPlan,
    ) -> tuple[PurchaseDemand, ...]: ...

    async def list_for_look(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
    ) -> tuple[PurchaseDemand, ...]: ...

    async def advance(
        self,
        *,
        user_id: UUID,
        demand_id: UUID,
        target: PurchaseDemandStatus,
    ) -> PurchaseDemand: ...
