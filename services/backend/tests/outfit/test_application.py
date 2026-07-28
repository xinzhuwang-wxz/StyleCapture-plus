from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from stylecapture_backend.features.capture.domain import CaptureSourceKind, OwnershipState
from stylecapture_backend.features.look.domain import (
    Look,
    LookComponent,
    LookDetail,
    PreferenceSignal,
)
from stylecapture_backend.features.outfit.application import (
    OutfitApplication,
    OutfitPlanInvalidError,
)
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitReasoningTrace,
    OutfitRecallRequirements,
    OutfitRequest,
    OutfitRerankResult,
    OutfitWorkflowTrace,
    PurchaseDemand,
    PurchaseDemandStatus,
)
from stylecapture_backend.features.outfit.infrastructure.tickets import (
    OutfitPlanTicketSigner,
)
from stylecapture_backend.features.outfit.interfaces.http import (
    OutfitHttpServices,
    build_outfit_router,
)
from stylecapture_backend.features.outfit.ports import OutfitPostSaveUnavailable
from stylecapture_backend.features.wardrobe.domain import (
    FieldEnvelope,
    FieldProvenance,
    ItemAttributes,
    ItemStatus,
    WardrobeItem,
)


class WardrobeStub:
    def __init__(self, items: list[WardrobeItem]) -> None:
        self.items = items
        self.recall_requirements: list[OutfitRecallRequirements] = []

    async def recall_for_outfit(
        self,
        *,
        user_id: UUID,
        requirements: OutfitRecallRequirements,
    ) -> list[WardrobeItem]:
        self.recall_requirements.append(requirements)
        allowed = set(requirements.required_roles)
        return [
            item
            for item in self.items
            if item.user_id == user_id
            and item.id not in requirements.exclude_item_ids
            and _test_category(item) in allowed
        ]

    async def get_for_user(
        self,
        item_id: UUID,
        user_id: UUID,
    ) -> WardrobeItem | None:
        return next(
            (item for item in self.items if item.id == item_id and item.user_id == user_id),
            None,
        )


class LookRepositoryStub:
    def __init__(self) -> None:
        self.looks: dict[UUID, Look] = {}
        self.components: dict[UUID, list[LookComponent]] = {}
        self.preferences: list[PreferenceSignal] = []

    async def save(self, look: Look) -> Look:
        existing = next(
            (
                candidate
                for candidate in self.looks.values()
                if candidate.capture_id == look.capture_id
                and candidate.source_selection_key == look.source_selection_key
            ),
            None,
        )
        if existing is not None:
            return existing
        self.looks[look.id] = look
        return look

    async def save_bundle(
        self,
        look: Look,
        components: tuple[LookComponent, ...],
        signal: PreferenceSignal,
    ) -> Look:
        stored = await self.save(look)
        for component in components:
            await self.save_component(
                LookComponent(
                    id=component.id,
                    look_id=stored.id,
                    component_key=component.component_key,
                    status=component.status,
                    item_id=component.item_id,
                    evidence_region=component.evidence_region,
                    role=component.role,
                    layer=component.layer,
                    display_order=component.display_order,
                    confidence=component.confidence,
                    grounding_metadata=component.grounding_metadata,
                    created_at=component.created_at,
                    updated_at=component.updated_at,
                )
            )
        await self.append_preference(
            PreferenceSignal(
                id=signal.id,
                user_id=signal.user_id,
                look_id=stored.id,
                kind=signal.kind,
                payload=signal.payload,
                idempotency_key=signal.idempotency_key,
                created_at=signal.created_at,
            )
        )
        return stored

    async def save_component(self, component: LookComponent) -> LookComponent:
        stored = self.components.setdefault(component.look_id, [])
        stored[:] = [
            candidate for candidate in stored if candidate.component_key != component.component_key
        ]
        stored.append(component)
        return component

    async def append_preference(
        self,
        signal: PreferenceSignal,
    ) -> PreferenceSignal:
        existing = next(
            (
                candidate
                for candidate in self.preferences
                if candidate.user_id == signal.user_id
                and candidate.idempotency_key == signal.idempotency_key
            ),
            None,
        )
        if existing is not None:
            return existing
        self.preferences.append(signal)
        return signal

    async def ensure_placeholder(
        self,
        look: Look,
        signal: PreferenceSignal,
    ) -> Look:
        raise NotImplementedError

    async def get_by_capture(
        self,
        capture_id: UUID,
        source_selection_key: str,
    ) -> Look | None:
        return next(
            (
                look
                for look in self.looks.values()
                if look.capture_id == capture_id
                and look.source_selection_key == source_selection_key
            ),
            None,
        )

    async def list_for_user(self, user_id: UUID) -> list[Look]:
        return [look for look in self.looks.values() if look.user_id == user_id]

    async def get_detail_for_user(
        self,
        look_id: UUID,
        user_id: UUID,
    ) -> LookDetail | None:
        look = self.looks.get(look_id)
        if look is None or look.user_id != user_id:
            return None
        return LookDetail(
            look=look,
            components=tuple(self.components.get(look_id, [])),
            preference_signals=tuple(
                signal for signal in self.preferences if signal.look_id == look_id
            ),
        )


class PresentationSchedulerStub:
    def __init__(
        self,
        *,
        fail_once: bool = False,
        failure: Exception | None = None,
    ) -> None:
        self.look_ids: list[UUID] = []
        self.fail_once = fail_once
        self.failure = failure or OutfitPostSaveUnavailable("temporary broker failure")

    async def enqueue_default_presentation(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
    ) -> None:
        if self.fail_once:
            self.fail_once = False
            raise self.failure
        self.look_ids.append(look_id)


class PurchaseDemandRepositoryStub:
    def __init__(self, *, fail_once: bool = False) -> None:
        self.look_ids: list[UUID] = []
        self.fail_once = fail_once

    async def ensure_for_plan(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
        plan: OutfitPlan,
    ) -> tuple[PurchaseDemand, ...]:
        if self.fail_once:
            self.fail_once = False
            raise OutfitPostSaveUnavailable("temporary database failure")
        self.look_ids.append(look_id)
        return ()

    async def list_for_look(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
    ) -> tuple[PurchaseDemand, ...]:
        return ()

    async def advance(
        self,
        *,
        user_id: UUID,
        demand_id: UUID,
        target: PurchaseDemandStatus,
    ) -> PurchaseDemand:
        raise NotImplementedError


class WorkflowTraceRepositoryStub:
    def __init__(self) -> None:
        self.traces: dict[UUID, OutfitWorkflowTrace] = {}

    async def save(self, trace: OutfitWorkflowTrace) -> OutfitWorkflowTrace:
        existing = self.traces.get(trace.id)
        if existing is not None:
            trace = OutfitWorkflowTrace(
                id=trace.id,
                user_id=trace.user_id,
                request_id=trace.request_id,
                status=trace.status,
                explanation_state=trace.explanation_state,
                plan_count=trace.plan_count,
                capability_alias=trace.capability_alias,
                model_version=trace.model_version,
                created_at=existing.created_at,
                updated_at=trace.updated_at,
            )
        self.traces[trace.id] = trace
        return trace

    async def get_for_user(
        self,
        *,
        trace_id: UUID,
        user_id: UUID,
    ) -> OutfitWorkflowTrace | None:
        trace = self.traces.get(trace_id)
        return trace if trace is not None and trace.user_id == user_id else None


class ChineseReranker:
    async def rerank(
        self,
        request: OutfitRequest,
        plans: tuple[OutfitPlan, ...],
    ) -> OutfitRerankResult:
        return OutfitRerankResult(
            plans=tuple(
                plan.with_ranking(
                    rationale=f"{request.scene}下强调真实衣橱的色彩与层次关系",
                    score=95 - index,
                )
                for index, plan in enumerate(reversed(plans))
            ),
            trace=OutfitReasoningTrace(
                capability_alias="reasoning",
                model_version="test-model",
                prompt_version="test-prompt-v1",
                schema_version="test-schema-v1",
                latency_ms=12,
            ),
        )


class MutatingReranker:
    async def rerank(
        self,
        request: OutfitRequest,
        plans: tuple[OutfitPlan, ...],
    ) -> OutfitRerankResult:
        first = plans[0]
        mutated = OutfitPlan(
            id=first.id,
            title=first.title,
            scene=first.scene,
            slots=tuple(reversed(first.slots)),
            rationale="模型错误地改变了候选结构",
            style_match_score=99,
        )
        return OutfitRerankResult(
            plans=(mutated, *plans[1:]),
            trace=OutfitReasoningTrace(
                capability_alias="reasoning",
                model_version="test-model",
                prompt_version="test-prompt-v1",
                schema_version="test-schema-v1",
                latency_ms=12,
            ),
        )


def item(
    user_id: UUID,
    *,
    category: str,
    description: str,
    ownership: OwnershipState = OwnershipState.OWNED,
    extra_fields: dict[str, object] | None = None,
) -> WardrobeItem:
    now = datetime.now(UTC)
    fields = {
        "category": FieldEnvelope(
            value=category,
            provenance=FieldProvenance.MODEL,
            confidence=0.98,
            model_version="vision-v1",
            locked=False,
        ),
        "description": FieldEnvelope(
            value=description,
            provenance=FieldProvenance.MODEL,
            confidence=0.94,
            model_version="vision-v1",
            locked=False,
        ),
    }
    fields.update(
        {
            name: FieldEnvelope(
                value=value,
                provenance=FieldProvenance.MODEL,
                confidence=0.9,
                model_version="vision-v1",
                locked=False,
            )
            for name, value in (extra_fields or {}).items()
        }
    )
    return WardrobeItem(
        id=uuid4(),
        user_id=user_id,
        capture_id=uuid4(),
        selection_key=f"item_{uuid4().hex[:8]}",
        source_object_key=f"uploads/{uuid4()}.jpg",
        display_object_key=f"derived/{uuid4()}.png",
        source_available=True,
        source_kind=CaptureSourceKind.UPLOAD,
        ownership=ownership,
        status=ItemStatus.READY,
        attributes=ItemAttributes(fields),
        model_metadata={},
        embedding=None,
        created_at=now,
        updated_at=now,
    )


def _test_category(item: WardrobeItem) -> OutfitCategory | None:
    value = str(item.attributes.fields["category"].value)
    if value in {"bags", "headwear", "accessories"}:
        return OutfitCategory.ACCESSORY
    try:
        return OutfitCategory(value)
    except ValueError:
        return None


@pytest.mark.asyncio
async def test_real_wardrobe_builds_four_plans_and_missing_search_demands() -> None:
    user_id = uuid4()
    application = OutfitApplication(
        wardrobe=WardrobeStub(
            [
                item(user_id, category="tops", description="米白针织上衣"),
                item(user_id, category="bottoms", description="棕色半身裙"),
            ]
        ),
        reranker=None,
    )

    result = await application.plan(
        user_id=user_id,
        request=OutfitRequest(scene="周五面试", style="复古通勤"),
    )

    assert len(result.plans) == 4
    assert result.degraded is True
    assert all(plan.wardrobe_item_ids for plan in result.plans)
    assert all(plan.missing_count >= 1 for plan in result.plans)
    assert all(
        all(slot.role is not OutfitCategory.DRESS for slot in plan.slots) for plan in result.plans
    )
    assert any(
        slot.search_query is not None and slot.search_query.startswith("复古通勤 鞋")
        for plan in result.plans
        for slot in plan.slots
    )


@pytest.mark.asyncio
async def test_reasoning_only_reranks_closed_candidates_and_returns_chinese_explanations() -> None:
    user_id = uuid4()
    application = OutfitApplication(
        wardrobe=WardrobeStub(
            [
                item(user_id, category="tops", description="白衬衫"),
                item(user_id, category="bottoms", description="黑色西裤"),
                item(user_id, category="shoes", description="黑色乐福鞋"),
            ]
        ),
        reranker=ChineseReranker(),
    )

    result = await application.plan(
        user_id=user_id,
        request=OutfitRequest(scene="客户提案", style="简洁正式"),
    )

    assert result.degraded is False
    assert result.explanation_state == "llm_ranked"
    assert all("客户提案" in plan.rationale for plan in result.plans)
    assert all(plan.style_match_score >= 92 for plan in result.plans)


@pytest.mark.asyncio
async def test_scene_semantics_change_real_items_and_each_result_has_visible_variety() -> None:
    user_id = uuid4()
    wardrobe = WardrobeStub(
        [
            item(
                user_id,
                category="tops",
                description="白色衬衫",
                extra_fields={"styles": ["通勤", "正式", "利落"]},
            ),
            item(
                user_id,
                category="tops",
                description="亮黄色短袖",
                extra_fields={"styles": ["旅行", "度假", "明亮", "拍照"]},
            ),
            item(
                user_id,
                category="bottoms",
                description="黑色西裤",
                extra_fields={"styles": ["通勤", "正式", "面试"]},
            ),
            item(
                user_id,
                category="bottoms",
                description="浅色短裤",
                extra_fields={"styles": ["旅行", "度假", "方便走路"]},
            ),
            item(
                user_id,
                category="shoes",
                description="棕色乐福鞋",
                extra_fields={"styles": ["通勤", "正式"]},
            ),
            item(
                user_id,
                category="shoes",
                description="白色运动鞋",
                extra_fields={"styles": ["旅行", "运动", "方便走路"]},
            ),
            item(user_id, category="outerwear", description="米色针织外套"),
            item(user_id, category="accessories", description="亮色拍照发带"),
        ]
    )
    application = OutfitApplication(wardrobe=wardrobe, reranker=None)

    travel = await application.plan(
        user_id=user_id,
        request=OutfitRequest(
            scene="旅行拍照，显眼但方便走路",  # noqa: RUF001
            weather="炎热高温",
            formality="轻松休闲",
            comfort="方便走路",
        ),
    )
    interview = await application.plan(
        user_id=user_id,
        request=OutfitRequest(
            scene="通勤面试，利落但不刻板",  # noqa: RUF001
            weather="温和",
            formality="正式商务",
            comfort="久坐舒适",
        ),
    )

    assert travel.plans[0].wardrobe_item_ids != interview.plans[0].wardrobe_item_ids
    travel_names = {slot.item_name for slot in travel.plans[0].slots}
    interview_names = {slot.item_name for slot in interview.plans[0].slots}
    assert "亮黄色短袖" in travel_names
    assert "白色运动鞋" in travel_names
    assert "白色衬衫" in interview_names
    assert "棕色乐福鞋" in interview_names
    assert len({plan.structure_signature for plan in travel.plans}) == 4
    assert len({plan.wardrobe_item_ids for plan in travel.plans}) == 4


@pytest.mark.asyncio
async def test_required_excluded_and_weather_constraints_are_applied_before_ranking() -> None:
    user_id = uuid4()
    required_top = item(user_id, category="tops", description="白色通勤衬衫")
    excluded_bottom = item(user_id, category="bottoms", description="黑色西裤")
    hot_weather_coat = item(user_id, category="outerwear", description="秋冬厚重羊毛大衣")
    alternative_bottom = item(user_id, category="bottoms", description="米色半身裙")
    wardrobe = WardrobeStub(
        [
            required_top,
            excluded_bottom,
            hot_weather_coat,
            alternative_bottom,
            item(user_id, category="shoes", description="黑色乐福鞋"),
        ]
    )
    application = OutfitApplication(
        wardrobe=wardrobe,
        reranker=None,
    )

    result = await application.plan(
        user_id=user_id,
        request=OutfitRequest(
            scene="夏日客户拜访",
            weather="炎热高温",
            formality="正式商务",
            must_include_item_ids=(required_top.id,),
            exclude_item_ids=(excluded_bottom.id,),
        ),
    )

    assert len(result.plans) == 4
    assert all(required_top.id in plan.wardrobe_item_ids for plan in result.plans)
    assert all(excluded_bottom.id not in plan.wardrobe_item_ids for plan in result.plans)
    assert all(hot_weather_coat.id not in plan.wardrobe_item_ids for plan in result.plans)
    signatures = {
        tuple((slot.role, slot.item_id, slot.search_query) for slot in plan.slots)
        for plan in result.plans
    }
    assert len(signatures) == 4
    recalled = wardrobe.recall_requirements[0]
    assert recalled.scene == "夏日客户拜访"
    assert recalled.weather == "炎热高温"
    assert recalled.formality == "正式商务"
    assert recalled.season == "夏季"
    assert recalled.exclude_item_ids == (excluded_bottom.id,)
    assert set(recalled.required_roles) == set(OutfitCategory)


@pytest.mark.asyncio
async def test_illegal_llm_candidate_mutation_degrades_to_valid_rule_candidates() -> None:
    user_id = uuid4()
    application = OutfitApplication(
        wardrobe=WardrobeStub(
            [
                item(user_id, category="tops", description="白衬衫"),
                item(user_id, category="bottoms", description="黑色西裤"),
                item(user_id, category="shoes", description="黑色乐福鞋"),
            ]
        ),
        reranker=MutatingReranker(),
    )

    result = await application.plan(
        user_id=user_id,
        request=OutfitRequest(scene="客户提案", style="简洁正式"),
    )

    assert result.degraded is True
    assert result.degradation_reason == "reasoning_temporarily_unavailable"
    assert result.explanation_state == "rule_ranked"
    assert len(result.plans) == 4
    assert len({plan.structure_signature for plan in result.plans}) == 4


@pytest.mark.asyncio
async def test_conflicting_required_dress_and_top_are_rejected() -> None:
    user_id = uuid4()
    dress = item(user_id, category="dresses", description="蓝色连衣裙")
    top = item(user_id, category="tops", description="白色衬衫")
    application = OutfitApplication(
        wardrobe=WardrobeStub([dress, top]),
        reranker=None,
    )

    with pytest.raises(OutfitPlanInvalidError, match="连衣裙"):
        await application.plan(
            user_id=user_id,
            request=OutfitRequest(
                scene="晚宴",
                must_include_item_ids=(dress.id, top.id),
            ),
        )


@pytest.mark.asyncio
async def test_required_dress_still_produces_four_structurally_distinct_plans() -> None:
    user_id = uuid4()
    dress = item(user_id, category="dresses", description="深蓝连衣裙")
    application = OutfitApplication(
        wardrobe=WardrobeStub(
            [
                dress,
                item(user_id, category="outerwear", description="黑色短外套"),
                item(user_id, category="shoes", description="黑色低跟鞋"),
                item(user_id, category="accessories", description="银色耳饰"),
            ]
        ),
        reranker=None,
    )

    result = await application.plan(
        user_id=user_id,
        request=OutfitRequest(
            scene="晚宴",
            must_include_item_ids=(dress.id,),
        ),
    )

    assert len(result.plans) == 4
    assert len({plan.id for plan in result.plans}) == 4
    assert all(dress.id in plan.wardrobe_item_ids for plan in result.plans)


@pytest.mark.asyncio
async def test_replacing_one_slot_keeps_every_other_slot_unchanged() -> None:
    user_id = uuid4()
    first_top = item(user_id, category="tops", description="白衬衫")
    second_top = item(user_id, category="tops", description="针织上衣")
    application = OutfitApplication(
        wardrobe=WardrobeStub(
            [
                first_top,
                second_top,
                item(user_id, category="bottoms", description="黑色西裤"),
                item(user_id, category="shoes", description="乐福鞋"),
            ]
        ),
        reranker=None,
    )
    plan = (
        await application.plan(
            user_id=user_id,
            request=OutfitRequest(
                scene="客户提案",
                must_include_item_ids=(first_top.id,),
            ),
        )
    ).plans[0]

    replaced = await application.replace_slot(
        user_id=user_id,
        plan=plan,
        role=OutfitCategory.TOP,
        request=OutfitRequest(
            scene="客户提案",
            must_include_item_ids=(first_top.id,),
        ),
    )

    before_other = tuple(slot for slot in plan.slots if slot.role is not OutfitCategory.TOP)
    after_other = tuple(slot for slot in replaced.slots if slot.role is not OutfitCategory.TOP)
    assert after_other == before_other
    assert next(slot.item_id for slot in replaced.slots if slot.role is OutfitCategory.TOP) == (
        second_top.id
    )


@pytest.mark.asyncio
async def test_stream_returns_each_real_draft_before_final_ai_refinement() -> None:
    user_id = uuid4()
    traces = WorkflowTraceRepositoryStub()
    application = OutfitApplication(
        wardrobe=WardrobeStub(
            [
                item(user_id, category="tops", description="白衬衫"),
                item(user_id, category="bottoms", description="黑色西裤"),
                item(user_id, category="shoes", description="黑色乐福鞋"),
            ]
        ),
        reranker=ChineseReranker(),
        traces=traces,
    )
    app = FastAPI()
    app.include_router(
        build_outfit_router(
            OutfitHttpServices(
                outfits=application,
                tickets=OutfitPlanTicketSigner("test-outfit-signing-secret-with-enough-entropy"),
            ),
            current_user=lambda: user_id,
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/v1/outfit-plans/stream",
            json={"scene": "客户提案", "style": "简洁正式"},
        )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.iter_lines()]
    assert [event["type"] for event in events] == [
        "plan",
        "plan",
        "plan",
        "plan",
        "complete",
    ]
    assert all(event["plan"]["rationale"] for event in events[:4])
    final = events[-1]["result"]
    assert final["explanation_state"] == "llm_ranked"
    assert all("客户提案" in plan["rationale"] for plan in final["plans"])
    assert all(event["trace_id"] == final["trace_id"] for event in events[:4])

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        trace_response = await client.get(f"/v1/outfit-plans/traces/{final['trace_id']}")

    assert trace_response.status_code == 200
    trace = trace_response.json()
    assert trace["request_id"] == final["request_id"]
    assert trace["status"] == "completed"
    assert trace["explanation_state"] == "llm_ranked"
    assert trace["plan_count"] == 4
    assert trace["capability_alias"] == "reasoning"
    assert trace["model_version"] == "test-model"
    assert trace["steps"][-1] == {
        "name": "reasoning_rerank",
        "label": "搭配理解与重排",
        "status": "completed",
    }
    serialized = json.dumps(trace)
    assert "prompt" not in serialized
    assert "media" not in serialized
    assert "provider" not in serialized


@pytest.mark.asyncio
async def test_selected_plan_becomes_ready_look_and_queues_default_presentation() -> None:
    user_id = uuid4()
    wardrobe = WardrobeStub(
        [
            item(
                user_id,
                category="tops",
                description="白衬衫",
                extra_fields={
                    "colors": ["象牙白"],
                    "style": ["利落", "通勤"],
                    "subcategory": "衬衫",
                },
            ),
            item(
                user_id,
                category="bottoms",
                description="黑色西裤",
                extra_fields={
                    "colors": ["黑色"],
                    "style": ["正式"],
                    "subcategory": "西裤",
                },
            ),
            item(
                user_id,
                category="shoes",
                description="黑色乐福鞋",
                extra_fields={
                    "colors": ["黑色"],
                    "style": ["通勤"],
                    "subcategory": "乐福鞋",
                },
            ),
        ]
    )
    looks = LookRepositoryStub()
    presentation = PresentationSchedulerStub()
    purchases = PurchaseDemandRepositoryStub(fail_once=True)
    application = OutfitApplication(
        wardrobe=wardrobe,
        reranker=ChineseReranker(),
        looks=looks,
        presentation=presentation,
        purchases=purchases,
    )
    result = await application.plan(
        user_id=user_id,
        request=OutfitRequest(scene="客户提案", style="简洁正式"),
    )
    plan = max(result.plans, key=lambda candidate: len(candidate.wardrobe_item_ids))

    saved_result = await application.save_plan_as_look(
        user_id=user_id,
        plan=plan,
        explanation_state=result.explanation_state,
        reasoning_trace=result.reasoning_trace,
        idempotency_key="save-plan-once",
    )
    saved = saved_result.look

    assert saved_result.presentation_state == "pending_retry"
    assert saved.source == "ai_generated"
    assert saved.capture_id is None
    assert saved.status == "ready"
    assert saved.analysis is not None
    assert saved.analysis.scene.value == "客户提案"
    assert saved.analysis.color.value == "象牙白、黑色"
    assert saved.analysis.silhouette.value == "利落、通勤、正式"
    assert saved.analysis.material.value == "衬衫、西裤、乐福鞋"
    assert saved.analysis.metadata.model_version == "test-model"
    assert saved.analysis.metadata.latency_ms == 12
    assert len(looks.components[saved.id]) == len(plan.wardrobe_item_ids)
    assert all(component.item_id is not None for component in looks.components[saved.id])
    assert all(component.evidence_region == () for component in looks.components[saved.id])
    assert all(component.confidence == 0 for component in looks.components[saved.id])
    assert all(
        component.grounding_metadata["item_version"] for component in looks.components[saved.id]
    )
    assert purchases.look_ids == []
    assert presentation.look_ids == []

    repeated_result = await application.save_plan_as_look(
        user_id=user_id,
        plan=plan,
        explanation_state=result.explanation_state,
        reasoning_trace=result.reasoning_trace,
        idempotency_key="save-plan-once",
    )
    repeated = repeated_result.look
    assert repeated.id == saved.id
    assert repeated_result.presentation_state == "queued"
    assert len(looks.components[saved.id]) == len(plan.wardrobe_item_ids)
    assert purchases.look_ids == [saved.id]
    assert presentation.look_ids == [saved.id]

    buggy_application = OutfitApplication(
        wardrobe=wardrobe,
        reranker=ChineseReranker(),
        looks=looks,
        presentation=PresentationSchedulerStub(
            fail_once=True,
            failure=RuntimeError("programming defect"),
        ),
        purchases=PurchaseDemandRepositoryStub(),
    )
    with pytest.raises(RuntimeError, match="programming defect"):
        await buggy_application.save_plan_as_look(
            user_id=user_id,
            plan=plan,
            explanation_state=result.explanation_state,
            reasoning_trace=result.reasoning_trace,
            idempotency_key="save-plan-programming-defect",
        )


def test_hot_weather_does_not_force_an_outer_layer() -> None:
    """大热天不该硬凑一件外套。

    八个模板里有六个带 OUTERWEAR，所以只要不特别排除，炎热高温下几乎每套
    都会塞一件外套——真机上表现为同一件针织开衫出现在所有推荐里，连炎热
    高温也不例外。
    """
    from stylecapture_backend.features.outfit.application import _is_hot

    assert _is_hot("炎热高温")
    assert _is_hot("盛夏闷热")
    assert not _is_hot("寒冷低温")
    assert not _is_hot("温和")
    assert not _is_hot(None)
