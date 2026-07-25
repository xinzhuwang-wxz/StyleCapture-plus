from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from stylecapture_backend.features.outfit.application import OutfitApplication
from stylecapture_backend.features.outfit.domain import (
    OutfitPlan,
    OutfitPlanSet,
    OutfitRequest,
    OutfitSlot,
)
from stylecapture_backend.platform.errors import STABLE_ERROR_RESPONSES


@dataclass(frozen=True, slots=True)
class OutfitHttpServices:
    outfits: OutfitApplication


class OutfitRequestBody(BaseModel):
    scene: str = Field(min_length=1, max_length=200)
    style: str | None = Field(default=None, max_length=120)
    weather: str | None = Field(default=None, max_length=120)
    comfort: str | None = Field(default=None, max_length=120)
    anchor_item_id: UUID | None = None


class OutfitSlotResponse(BaseModel):
    role: str
    item_id: UUID | None
    item_name: str | None
    ownership: str | None
    image_url: str | None
    search_query: str | None

    @classmethod
    def from_domain(cls, slot: OutfitSlot) -> OutfitSlotResponse:
        return cls(
            role=slot.role.value,
            item_id=slot.item_id,
            item_name=slot.item_name,
            ownership=slot.ownership,
            image_url=slot.image_url,
            search_query=slot.search_query,
        )


class OutfitPlanResponse(BaseModel):
    id: UUID
    title: str
    scene: str
    slots: list[OutfitSlotResponse]
    rationale: str
    style_match_score: int
    missing_count: int

    @classmethod
    def from_domain(cls, plan: OutfitPlan) -> OutfitPlanResponse:
        return cls(
            id=plan.id,
            title=plan.title,
            scene=plan.scene,
            slots=[OutfitSlotResponse.from_domain(slot) for slot in plan.slots],
            rationale=plan.rationale,
            style_match_score=plan.style_match_score,
            missing_count=plan.missing_count,
        )


class OutfitPlanSetResponse(BaseModel):
    request_id: UUID
    plans: list[OutfitPlanResponse]
    degraded: bool
    degradation_reason: str | None
    explanation_state: str

    @classmethod
    def from_domain(cls, result: OutfitPlanSet) -> OutfitPlanSetResponse:
        return cls(
            request_id=result.request_id,
            plans=[OutfitPlanResponse.from_domain(plan) for plan in result.plans],
            degraded=result.degraded,
            degradation_reason=result.degradation_reason,
            explanation_state=result.explanation_state,
        )


def build_outfit_router(
    services: OutfitHttpServices,
    *,
    current_user: Callable[..., UUID],
) -> APIRouter:
    router = APIRouter(prefix="/v1/outfit-plans")
    principal = Depends(current_user)

    @router.post(
        "",
        response_model=OutfitPlanSetResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def create_outfit_plans(
        body: OutfitRequestBody,
        user_id: UUID = principal,
    ) -> OutfitPlanSetResponse:
        result = await services.outfits.plan(
            user_id=user_id,
            request=OutfitRequest(
                scene=body.scene,
                style=body.style,
                weather=body.weather,
                comfort=body.comfort,
                anchor_item_id=body.anchor_item_id,
            ),
        )
        return OutfitPlanSetResponse.from_domain(result)

    return router
