from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from stylecapture_backend.features.outfit.application import (
    OutfitApplication,
    outfit_trace_id,
)
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitPlanSet,
    OutfitRequest,
    OutfitSlot,
    OutfitWorkflowStatus,
    OutfitWorkflowTrace,
    PurchaseDemand,
    PurchaseDemandStatus,
)
from stylecapture_backend.features.outfit.ports import OutfitPlanTickets
from stylecapture_backend.platform.errors import STABLE_ERROR_RESPONSES


@dataclass(frozen=True, slots=True)
class OutfitHttpServices:
    outfits: OutfitApplication
    tickets: OutfitPlanTickets


class OutfitRequestBody(BaseModel):
    scene: str = Field(min_length=1, max_length=200)
    style: str | None = Field(default=None, max_length=120)
    weather: str | None = Field(default=None, max_length=120)
    formality: str | None = Field(default=None, max_length=120)
    comfort: str | None = Field(default=None, max_length=120)
    anchor_item_id: UUID | None = None
    must_include_item_ids: list[UUID] = Field(default_factory=list, max_length=8)
    exclude_item_ids: list[UUID] = Field(default_factory=list, max_length=40)


class OutfitSlotResponse(BaseModel):
    role: OutfitCategory
    item_id: UUID | None
    item_name: str | None
    ownership: str | None
    image_url: str | None
    search_query: str | None
    source_kind: str | None

    @classmethod
    def from_domain(cls, slot: OutfitSlot) -> OutfitSlotResponse:
        return cls(
            role=slot.role,
            item_id=slot.item_id,
            item_name=slot.item_name,
            ownership=slot.ownership,
            image_url=slot.image_url,
            search_query=slot.search_query,
            source_kind=slot.source_kind,
        )


class OutfitPlanResponse(BaseModel):
    id: UUID
    title: str
    scene: str
    slots: list[OutfitSlotResponse]
    rationale: str
    style_match_score: int
    missing_count: int
    save_token: str

    @classmethod
    def from_domain(
        cls,
        plan: OutfitPlan,
        *,
        save_token: str,
    ) -> OutfitPlanResponse:
        return cls(
            id=plan.id,
            title=plan.title,
            scene=plan.scene,
            slots=[OutfitSlotResponse.from_domain(slot) for slot in plan.slots],
            rationale=plan.rationale,
            style_match_score=plan.style_match_score,
            missing_count=plan.missing_count,
            save_token=save_token,
        )


class OutfitPlanSetResponse(BaseModel):
    request_id: UUID
    trace_id: UUID
    plans: list[OutfitPlanResponse]
    degraded: bool
    degradation_reason: str | None
    explanation_state: str

    @classmethod
    def from_domain(
        cls,
        result: OutfitPlanSet,
        *,
        user_id: UUID,
        tickets: OutfitPlanTickets,
        request: OutfitRequest,
    ) -> OutfitPlanSetResponse:
        return cls(
            request_id=result.request_id,
            trace_id=outfit_trace_id(
                user_id=user_id,
                request_id=result.request_id,
            ),
            plans=[
                OutfitPlanResponse.from_domain(
                    plan,
                    save_token=tickets.issue(
                        user_id=user_id,
                        plan=plan,
                        explanation_state=result.explanation_state,
                        request=request,
                        reasoning_trace=result.reasoning_trace,
                    ),
                )
                for plan in result.plans
            ],
            degraded=result.degraded,
            degradation_reason=result.degradation_reason,
            explanation_state=result.explanation_state,
        )


class SaveOutfitPlanBody(BaseModel):
    save_token: str = Field(min_length=40, max_length=20_000)


class ReplaceOutfitSlotBody(BaseModel):
    save_token: str = Field(min_length=40, max_length=20_000)
    role: OutfitCategory


class SavedOutfitLookResponse(BaseModel):
    look_id: UUID
    status: str
    presentation_state: str


class PurchaseDemandResponse(BaseModel):
    id: UUID
    look_id: UUID
    item_id: UUID | None
    role: OutfitCategory
    search_query: str
    search_url: str
    status: PurchaseDemandStatus
    can_mark_owned: bool

    @classmethod
    def from_domain(cls, demand: PurchaseDemand) -> PurchaseDemandResponse:
        return cls(
            id=demand.id,
            look_id=demand.look_id,
            item_id=demand.item_id,
            role=demand.role,
            search_query=demand.search_query,
            search_url=f"https://www.douyin.com/search/{quote(demand.search_query)}",
            status=demand.status,
            can_mark_owned=demand.can_mark_owned,
        )


class PurchaseDemandListResponse(BaseModel):
    demands: list[PurchaseDemandResponse]


class AdvancePurchaseDemandBody(BaseModel):
    status: PurchaseDemandStatus


class OutfitWorkflowStepResponse(BaseModel):
    name: str
    label: str
    status: str


class OutfitWorkflowTraceResponse(BaseModel):
    trace_id: UUID
    request_id: UUID
    status: OutfitWorkflowStatus
    explanation_state: str
    plan_count: int
    capability_alias: str
    model_version: str
    steps: list[OutfitWorkflowStepResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, trace: OutfitWorkflowTrace) -> OutfitWorkflowTraceResponse:
        reasoning_status = {
            OutfitWorkflowStatus.CANDIDATES_READY: "pending",
            OutfitWorkflowStatus.COMPLETED: "completed",
            OutfitWorkflowStatus.DEGRADED: "degraded",
        }[trace.status]
        return cls(
            trace_id=trace.id,
            request_id=trace.request_id,
            status=trace.status,
            explanation_state=trace.explanation_state,
            plan_count=trace.plan_count,
            capability_alias=trace.capability_alias,
            model_version=trace.model_version,
            steps=[
                OutfitWorkflowStepResponse(
                    name="wardrobe_recall",
                    label="读取真实数字衣橱",
                    status="completed",
                ),
                OutfitWorkflowStepResponse(
                    name="candidate_planning",
                    label="生成封闭穿搭候选",
                    status="completed",
                ),
                OutfitWorkflowStepResponse(
                    name="reasoning_rerank",
                    label="搭配理解与重排",
                    status=reasoning_status,
                ),
            ],
            created_at=trace.created_at,
            updated_at=trace.updated_at,
        )


def build_outfit_router(
    services: OutfitHttpServices,
    *,
    current_user: Callable[..., UUID],
) -> APIRouter:
    router = APIRouter(prefix="/v1/outfit-plans")
    principal = Depends(current_user)
    tickets = services.tickets

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
                formality=body.formality,
                comfort=body.comfort,
                anchor_item_id=body.anchor_item_id,
                must_include_item_ids=tuple(body.must_include_item_ids),
                exclude_item_ids=tuple(body.exclude_item_ids),
            ),
        )
        return OutfitPlanSetResponse.from_domain(
            result,
            user_id=user_id,
            tickets=tickets,
            request=OutfitRequest(
                scene=body.scene,
                style=body.style,
                weather=body.weather,
                formality=body.formality,
                comfort=body.comfort,
                anchor_item_id=body.anchor_item_id,
                must_include_item_ids=tuple(body.must_include_item_ids),
                exclude_item_ids=tuple(body.exclude_item_ids),
            ),
        )

    @router.post(
        "/stream",
        responses=STABLE_ERROR_RESPONSES,
    )
    async def stream_outfit_plans(
        body: OutfitRequestBody,
        user_id: UUID = principal,
    ) -> StreamingResponse:
        request = OutfitRequest(
            scene=body.scene,
            style=body.style,
            weather=body.weather,
            formality=body.formality,
            comfort=body.comfort,
            anchor_item_id=body.anchor_item_id,
            must_include_item_ids=tuple(body.must_include_item_ids),
            exclude_item_ids=tuple(body.exclude_item_ids),
        )
        drafts = await services.outfits.draft_plans(
            user_id=user_id,
            request=request,
        )

        async def stream() -> AsyncIterator[str]:
            for plan in drafts.plans:
                yield (
                    json.dumps(
                        {
                            "type": "plan",
                            "request_id": str(drafts.request_id),
                            "trace_id": str(
                                outfit_trace_id(
                                    user_id=user_id,
                                    request_id=drafts.request_id,
                                )
                            ),
                            "plan": OutfitPlanResponse.from_domain(
                                plan,
                                save_token=tickets.issue(
                                    user_id=user_id,
                                    plan=plan,
                                    explanation_state=drafts.explanation_state,
                                    request=request,
                                    reasoning_trace=drafts.reasoning_trace,
                                ),
                            ).model_dump(mode="json"),
                            "plan_count": len(drafts.plans),
                            "explanation_state": drafts.explanation_state,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                await asyncio.sleep(0.04)
            result = await services.outfits.refine_plans(
                user_id=user_id,
                request=request,
                drafts=drafts,
            )
            yield (
                json.dumps(
                    {
                        "type": "complete",
                        "result": OutfitPlanSetResponse.from_domain(
                            result,
                            user_id=user_id,
                            tickets=tickets,
                            request=request,
                        ).model_dump(mode="json"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

        return StreamingResponse(
            stream(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get(
        "/traces/{trace_id}",
        response_model=OutfitWorkflowTraceResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_outfit_workflow_trace(
        trace_id: UUID,
        user_id: UUID = principal,
    ) -> OutfitWorkflowTraceResponse:
        trace = await services.outfits.get_workflow_trace(
            user_id=user_id,
            trace_id=trace_id,
        )
        return OutfitWorkflowTraceResponse.from_domain(trace)

    @router.post(
        "/{plan_id}/save-look",
        response_model=SavedOutfitLookResponse,
        status_code=status.HTTP_201_CREATED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def save_outfit_plan(
        plan_id: UUID,
        body: SaveOutfitPlanBody,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        user_id: UUID = principal,
    ) -> SavedOutfitLookResponse:
        plan, explanation_state, _request, reasoning_trace = tickets.verify(
            body.save_token,
            user_id=user_id,
            expected_plan_id=plan_id,
        )
        saved = await services.outfits.save_plan_as_look(
            user_id=user_id,
            plan=plan,
            explanation_state=explanation_state,
            reasoning_trace=reasoning_trace,
            idempotency_key=idempotency_key,
        )
        return SavedOutfitLookResponse(
            look_id=saved.look.id,
            status=saved.look.status.value,
            presentation_state=saved.presentation_state,
        )

    @router.post(
        "/{plan_id}/replace-slot",
        response_model=OutfitPlanResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def replace_outfit_slot(
        plan_id: UUID,
        body: ReplaceOutfitSlotBody,
        user_id: UUID = principal,
    ) -> OutfitPlanResponse:
        plan, explanation_state, request, reasoning_trace = tickets.verify(
            body.save_token,
            user_id=user_id,
            expected_plan_id=plan_id,
        )
        replaced = await services.outfits.replace_slot(
            user_id=user_id,
            plan=plan,
            role=body.role,
            request=request,
        )
        return OutfitPlanResponse.from_domain(
            replaced,
            save_token=tickets.issue(
                user_id=user_id,
                plan=replaced,
                explanation_state=explanation_state,
                request=request,
                reasoning_trace=reasoning_trace,
            ),
        )

    @router.get(
        "/saved-looks/{look_id}/purchase-list",
        response_model=PurchaseDemandListResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def list_purchase_demands(
        look_id: UUID,
        user_id: UUID = principal,
    ) -> PurchaseDemandListResponse:
        demands = await services.outfits.list_purchase_demands(
            user_id=user_id,
            look_id=look_id,
        )
        return PurchaseDemandListResponse(
            demands=[PurchaseDemandResponse.from_domain(demand) for demand in demands]
        )

    @router.patch(
        "/purchase-demands/{demand_id}",
        response_model=PurchaseDemandResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def advance_purchase_demand(
        demand_id: UUID,
        body: AdvancePurchaseDemandBody,
        user_id: UUID = principal,
    ) -> PurchaseDemandResponse:
        demand = await services.outfits.advance_purchase_demand(
            user_id=user_id,
            demand_id=demand_id,
            target=body.status,
        )
        return PurchaseDemandResponse.from_domain(demand)

    return router
