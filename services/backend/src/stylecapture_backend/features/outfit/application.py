from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid5

from stylecapture_backend.features.capture.domain import OwnershipState
from stylecapture_backend.features.look.domain import (
    COMPOSITION_ITEM_EVIDENCE,
    Look,
    LookAnalysis,
    LookAnalysisField,
    LookAnalysisMetadata,
    LookComponent,
    PreferenceSignal,
)
from stylecapture_backend.features.look.ports import LookRepository
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitPlanSet,
    OutfitReasoningTrace,
    OutfitRecallRequirements,
    OutfitRequest,
    OutfitSlot,
    OutfitWorkflowStatus,
    OutfitWorkflowTrace,
    PurchaseDemand,
    PurchaseDemandStatus,
)
from stylecapture_backend.features.outfit.ports import (
    OutfitPostSaveUnavailable,
    OutfitPresentationScheduler,
    OutfitReranker,
    OutfitWardrobeReader,
    OutfitWorkflowTraceRepository,
    PurchaseDemandRepository,
)
from stylecapture_backend.features.wardrobe.domain import ItemStatus, WardrobeItem

PLAN_NAMESPACE = UUID("7fb45e4c-8de2-48d2-9652-ec5463a42e65")
TRACE_NAMESPACE = UUID("91459d67-5cf8-4b33-aee9-b7b24b7dd183")
logger = logging.getLogger(__name__)

# The recommender keeps hard constraints deterministic, but Chinese scene prompts
# rarely contain whitespace. Expand those phrases before scoring so the
# closed candidates handed to LiteLLM actually respond to the user's intent.
QUERY_CONCEPTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("旅行", ("旅行", "度假", "轻便", "户外")),
    ("拍照", ("拍照", "明亮", "明快", "亮色", "浪漫", "显眼")),
    ("通勤", ("通勤", "利落", "知性", "实用", "耐穿")),
    ("面试", ("面试", "通勤", "正式", "利落", "简洁", "得体")),
    ("约会", ("约会", "浪漫", "温柔", "甜美", "松弛")),
    ("上课", ("上课", "学院", "日常", "休闲", "舒适", "耐穿")),
    ("炎热", ("炎热", "夏日", "夏季", "轻便", "清爽")),
    ("寒冷", ("寒冷", "秋冬", "冬季", "保暖", "叠穿")),
    ("正式", ("正式", "商务", "通勤", "利落", "优雅")),
    ("休闲", ("休闲", "松弛", "日常", "舒适")),
    ("走路", ("走路", "轻便", "运动", "耐穿", "舒适")),
    ("久坐", ("久坐", "舒适", "松弛", "柔软")),
)

TEMPLATES: tuple[tuple[OutfitCategory, ...], ...] = (
    (
        OutfitCategory.TOP,
        OutfitCategory.BOTTOM,
        OutfitCategory.OUTERWEAR,
        OutfitCategory.SHOES,
        OutfitCategory.ACCESSORY,
    ),
    (
        OutfitCategory.DRESS,
        OutfitCategory.OUTERWEAR,
        OutfitCategory.SHOES,
        OutfitCategory.ACCESSORY,
    ),
    (
        OutfitCategory.DRESS,
        OutfitCategory.SHOES,
        OutfitCategory.ACCESSORY,
    ),
    (
        OutfitCategory.DRESS,
        OutfitCategory.OUTERWEAR,
        OutfitCategory.SHOES,
    ),
    (
        OutfitCategory.DRESS,
        OutfitCategory.OUTERWEAR,
        OutfitCategory.ACCESSORY,
    ),
    (
        OutfitCategory.TOP,
        OutfitCategory.BOTTOM,
        OutfitCategory.SHOES,
        OutfitCategory.ACCESSORY,
    ),
    (
        OutfitCategory.TOP,
        OutfitCategory.BOTTOM,
        OutfitCategory.OUTERWEAR,
        OutfitCategory.SHOES,
    ),
    (
        OutfitCategory.TOP,
        OutfitCategory.BOTTOM,
        OutfitCategory.OUTERWEAR,
        OutfitCategory.ACCESSORY,
    ),
    # The three below carry no outer layer. Only two of the original eight did,
    # which is too few to build four distinct plans, so hot weather had to put
    # the coat back in.
    (
        OutfitCategory.TOP,
        OutfitCategory.BOTTOM,
        OutfitCategory.SHOES,
    ),
    (
        OutfitCategory.TOP,
        OutfitCategory.BOTTOM,
        OutfitCategory.ACCESSORY,
    ),
    (
        OutfitCategory.DRESS,
        OutfitCategory.SHOES,
    ),
)

ACCESSORY_CATEGORIES = {"bags", "headwear", "accessories"}


class OutfitWardrobeEmptyError(ValueError):
    """The user has no ready wardrobe assets that can form a plan."""


class OutfitPlanInvalidError(ValueError):
    """A selected plan no longer references valid wardrobe assets."""


class OutfitWorkflowTraceNotFoundError(LookupError):
    """The requested workflow trace does not belong to the current user."""


@dataclass(frozen=True, slots=True)
class SavedOutfitLook:
    look: Look
    presentation_state: str


class OutfitApplication:
    def __init__(
        self,
        *,
        wardrobe: OutfitWardrobeReader,
        reranker: OutfitReranker | None,
        looks: LookRepository | None = None,
        presentation: OutfitPresentationScheduler | None = None,
        purchases: PurchaseDemandRepository | None = None,
        traces: OutfitWorkflowTraceRepository | None = None,
    ) -> None:
        self._wardrobe = wardrobe
        self._reranker = reranker
        self._looks = looks
        self._presentation = presentation
        self._purchases = purchases
        self._traces = traces

    async def plan(
        self,
        *,
        user_id: UUID,
        request: OutfitRequest,
    ) -> OutfitPlanSet:
        drafts = await self.draft_plans(user_id=user_id, request=request)
        return await self.refine_plans(
            user_id=user_id,
            request=request,
            drafts=drafts,
        )

    async def draft_plans(
        self,
        *,
        user_id: UUID,
        request: OutfitRequest,
    ) -> OutfitPlanSet:
        all_items = tuple(
            item
            for item in await self._wardrobe.recall_for_outfit(
                user_id=user_id,
                requirements=_recall_requirements(
                    request,
                    required_roles=tuple(OutfitCategory),
                ),
            )
            if item.status in {ItemStatus.READY, ItemStatus.PARTIAL} and _category(item) is not None
        )
        if not all_items:
            raise OutfitWardrobeEmptyError("请先保存至少一件已识别的真实衣服")
        by_id = {item.id: item for item in all_items}
        required_items: list[WardrobeItem] = []
        for item_id in request.required_item_ids:
            item = by_id.get(item_id)
            if item is None:
                raise OutfitPlanInvalidError("必须使用的单品已变化, 请重新选择")
            required_items.append(item)
        _validate_required_items(tuple(required_items), request)
        items = tuple(item for item in all_items if item.id not in request.exclude_item_ids)
        plans = _build_plans(items, request)
        _validate_plan_hard_rules(plans, request=request, items=items)
        result = OutfitPlanSet(
            request_id=_request_id(user_id=user_id, request=request, plans=plans),
            plans=plans,
            degraded=False,
            degradation_reason=None,
            explanation_state="rule_ranked",
        )
        await self._record_workflow_trace(
            user_id=user_id,
            result=result,
            status=OutfitWorkflowStatus.CANDIDATES_READY,
        )
        return result

    async def refine_plans(
        self,
        *,
        user_id: UUID,
        request: OutfitRequest,
        drafts: OutfitPlanSet,
    ) -> OutfitPlanSet:
        if self._reranker is None:
            result = _degraded_drafts(drafts, "reasoning_not_configured")
            await self._record_workflow_trace(
                user_id=user_id,
                result=result,
                status=OutfitWorkflowStatus.DEGRADED,
            )
            return result
        try:
            reranked = await self._reranker.rerank(request, drafts.plans)
            _validate_reranked_plans(drafts.plans, reranked.plans)
        except Exception as exc:
            logger.warning(
                "Outfit reasoning degraded safely (%s)",
                type(exc).__name__,
            )
            result = _degraded_drafts(drafts, "reasoning_temporarily_unavailable")
            await self._record_workflow_trace(
                user_id=user_id,
                result=result,
                status=OutfitWorkflowStatus.DEGRADED,
            )
            return result
        result = OutfitPlanSet(
            request_id=drafts.request_id,
            plans=reranked.plans,
            degraded=False,
            degradation_reason=None,
            explanation_state="llm_ranked",
            reasoning_trace=reranked.trace,
        )
        await self._record_workflow_trace(
            user_id=user_id,
            result=result,
            status=OutfitWorkflowStatus.COMPLETED,
        )
        return result

    async def get_workflow_trace(
        self,
        *,
        user_id: UUID,
        trace_id: UUID,
    ) -> OutfitWorkflowTrace:
        if self._traces is None:
            raise OutfitWorkflowTraceNotFoundError(trace_id)
        trace = await self._traces.get_for_user(
            trace_id=trace_id,
            user_id=user_id,
        )
        if trace is None:
            raise OutfitWorkflowTraceNotFoundError(trace_id)
        return trace

    async def _record_workflow_trace(
        self,
        *,
        user_id: UUID,
        result: OutfitPlanSet,
        status: OutfitWorkflowStatus,
    ) -> None:
        if self._traces is None:
            return
        now = datetime.now(UTC)
        reasoning = result.reasoning_trace
        await self._traces.save(
            OutfitWorkflowTrace(
                id=outfit_trace_id(user_id=user_id, request_id=result.request_id),
                user_id=user_id,
                request_id=result.request_id,
                status=status,
                explanation_state=result.explanation_state,
                plan_count=len(result.plans),
                capability_alias=(
                    reasoning.capability_alias if reasoning is not None else "deterministic_rules"
                ),
                model_version=(
                    reasoning.model_version if reasoning is not None else "outfit-plan-rules-v1"
                ),
                created_at=now,
                updated_at=now,
            )
        )

    async def replace_slot(
        self,
        *,
        user_id: UUID,
        plan: OutfitPlan,
        role: OutfitCategory,
        request: OutfitRequest,
    ) -> OutfitPlan:
        current = next((slot for slot in plan.slots if slot.role is role), None)
        if current is None:
            raise OutfitPlanInvalidError("这套穿搭里没有可替换的这个位置")
        used_item_ids = {
            slot.item_id
            for slot in plan.slots
            if slot.item_id is not None and slot.role is not role
        }
        items = tuple(
            item
            for item in await self._wardrobe.recall_for_outfit(
                user_id=user_id,
                requirements=_recall_requirements(
                    request,
                    required_roles=(role,),
                    anchor_item_id=current.item_id,
                    additional_exclusions=tuple(
                        item_id for item_id in used_item_ids if item_id is not None
                    ),
                ),
            )
            if item.status in {ItemStatus.READY, ItemStatus.PARTIAL} and _category(item) is role
        )
        replacement_request = replace(
            request,
            anchor_item_id=(
                None if request.anchor_item_id == current.item_id else request.anchor_item_id
            ),
            must_include_item_ids=tuple(
                item_id for item_id in request.must_include_item_ids if item_id != current.item_id
            ),
        )
        candidates = tuple(
            item
            for item in _rank_items(items, role, replacement_request)
            if item.id != current.item_id and item.id not in used_item_ids
        )
        if not candidates:
            raise OutfitPlanInvalidError("衣橱里暂时没有另一件可替换的同类单品")
        replacement = _item_slot(role, candidates[0])
        slots = tuple(replacement if slot.role is role else slot for slot in plan.slots)
        signature = _slot_signature(slots)
        return OutfitPlan(
            id=uuid5(PLAN_NAMESPACE, f"replace:{plan.id}:{role.value}:{'|'.join(signature)}"),
            title=f"{plan.title} · 已换{_role_label(role)}",
            scene=plan.scene,
            slots=slots,
            rationale=f"只替换了{_role_label(role)}, 其余已选单品保持不变。",
            style_match_score=max(60, plan.style_match_score - 1),
        )

    async def save_plan_as_look(
        self,
        *,
        user_id: UUID,
        plan: OutfitPlan,
        explanation_state: str,
        reasoning_trace: OutfitReasoningTrace | None,
        idempotency_key: str,
    ) -> SavedOutfitLook:
        if self._looks is None:
            raise RuntimeError("outfit saving is not configured")
        request_key = idempotency_key.strip()
        if not request_key:
            raise ValueError("idempotency key must not be empty")
        item_ids = plan.wardrobe_item_ids
        if not item_ids:
            raise OutfitPlanInvalidError("至少需要一件真实衣橱单品才能保存穿搭")
        if len(set(item_ids)) != len(item_ids):
            raise OutfitPlanInvalidError("同一件单品不能在一套穿搭中重复出现")

        items: list[WardrobeItem] = []
        for item_id in item_ids:
            item = await self._wardrobe.get_for_user(item_id, user_id)
            if item is None or item.status not in {ItemStatus.READY, ItemStatus.PARTIAL}:
                raise OutfitPlanInvalidError("穿搭中的单品已变化, 请重新生成方案")
            items.append(item)

        source_selection_key = f"ai{plan.id.hex}"
        proposed = Look.ai_generated(
            user_id=user_id,
            source_selection_key=source_selection_key,
            analysis=_analysis_from_plan(
                plan,
                items,
                explanation_state,
                reasoning_trace,
            ),
        )
        item_by_id = {item.id: item for item in items}
        components: list[LookComponent] = []
        for display_order, slot in enumerate(
            slot for slot in plan.slots if slot.item_id is not None
        ):
            assert slot.item_id is not None
            item = item_by_id[slot.item_id]
            component = LookComponent.pending(
                look_id=proposed.id,
                component_key=f"slot{display_order + 1}",
                evidence_region=(),
                confidence=0.0,
                grounding_metadata={
                    "evidence_type": COMPOSITION_ITEM_EVIDENCE,
                    "plan_id": str(plan.id),
                    "item_id": str(item.id),
                    "item_capture_id": str(item.capture_id),
                    "item_source_object_key": item.source_object_key,
                    "item_display_object_key": item.display_object_key,
                    "item_selection_key": item.selection_key,
                    "item_version": item.updated_at.isoformat(),
                },
                role=slot.role.value,
                layer=str(display_order),
                display_order=display_order,
            ).with_item(item.id)
            components.append(component)
        signal = PreferenceSignal.look_saved(
            user_id=user_id,
            look_id=proposed.id,
            idempotency_key=f"outfit-save:{sha256(request_key.encode()).hexdigest()}",
        )
        stored = await self._looks.save_bundle(
            proposed,
            tuple(components),
            signal,
        )
        presentation_state = "not_configured"
        try:
            if self._purchases is not None:
                await self._purchases.ensure_for_plan(
                    user_id=user_id,
                    look_id=stored.id,
                    plan=plan,
                )
            if self._presentation is not None:
                await self._presentation.enqueue_default_presentation(
                    user_id=user_id,
                    look_id=stored.id,
                )
                presentation_state = "queued"
        except OutfitPostSaveUnavailable:
            logger.warning(
                "outfit post-save work requires idempotent retry",
                extra={"look_id": str(stored.id), "user_id": str(user_id)},
            )
            presentation_state = "pending_retry"
        return SavedOutfitLook(
            look=stored,
            presentation_state=presentation_state,
        )

    async def list_purchase_demands(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
    ) -> tuple[PurchaseDemand, ...]:
        if self._purchases is None:
            return ()
        return await self._purchases.list_for_look(
            user_id=user_id,
            look_id=look_id,
        )

    async def advance_purchase_demand(
        self,
        *,
        user_id: UUID,
        demand_id: UUID,
        target: PurchaseDemandStatus,
    ) -> PurchaseDemand:
        if self._purchases is None:
            raise OutfitPlanInvalidError("购买清单服务暂时不可用")
        try:
            return await self._purchases.advance(
                user_id=user_id,
                demand_id=demand_id,
                target=target,
            )
        except LookupError as error:
            raise OutfitPlanInvalidError("这条补齐需求不存在") from error
        except (ValueError, KeyError) as error:
            if target is PurchaseDemandStatus.OWNED:
                raise OutfitPlanInvalidError(
                    "只有关联了真实衣橱单品的购买需求才能确认入库, 其他商品收到后请先拍照上传"
                ) from error
            raise OutfitPlanInvalidError("购买状态只能按待购买、已下单推进") from error


def outfit_trace_id(*, user_id: UUID, request_id: UUID) -> UUID:
    return uuid5(TRACE_NAMESPACE, f"{user_id}:{request_id}")


def _analysis_from_plan(
    plan: OutfitPlan,
    items: list[WardrobeItem],
    explanation_state: str,
    reasoning_trace: OutfitReasoningTrace | None,
) -> LookAnalysis:
    def values_for(*names: str) -> str:
        values: list[str] = []
        for item in items:
            for name in names:
                field = item.attributes.fields.get(name)
                if field is None:
                    continue
                raw_values = (
                    field.value if isinstance(field.value, list | tuple) else (field.value,)
                )
                for raw_value in raw_values:
                    value = str(raw_value).strip()
                    if value and value not in values:
                        values.append(value)
        return "、".join(values) if values else "以真实单品为准"

    roles = " → ".join(_role_label(slot.role) for slot in plan.slots)
    model_state = (
        reasoning_trace.model_version if reasoning_trace is not None else "deterministic-rules"
    )
    confidence = 0.9 if explanation_state == "llm_ranked" else 0.75
    return LookAnalysis(
        color=LookAnalysisField(
            values_for("color_family", "color", "colors"),
            confidence,
        ),
        silhouette=LookAnalysisField(
            values_for("silhouette", "fit", "style"),
            confidence,
        ),
        material=LookAnalysisField(
            values_for("material", "fabric", "subcategory"),
            confidence,
        ),
        layering=LookAnalysisField(roles, confidence),
        focal_point=LookAnalysisField(plan.title, confidence),
        scene=LookAnalysisField(plan.scene, confidence),
        style=LookAnalysisField(plan.rationale, confidence),
        metadata=LookAnalysisMetadata(
            capability_alias=(
                reasoning_trace.capability_alias
                if reasoning_trace is not None
                else "deterministic_rules"
            ),
            model_version=model_state,
            prompt_version=(
                reasoning_trace.prompt_version
                if reasoning_trace is not None
                else "outfit-plan-rules-v1"
            ),
            schema_version=(
                reasoning_trace.schema_version
                if reasoning_trace is not None
                else "look-analysis-v1"
            ),
            taxonomy_version="wardrobe-taxonomy-v1",
            latency_ms=reasoning_trace.latency_ms if reasoning_trace is not None else 0,
        ),
    )


def _request_id(
    *,
    user_id: UUID,
    request: OutfitRequest,
    plans: tuple[OutfitPlan, ...],
) -> UUID:
    return uuid5(
        PLAN_NAMESPACE,
        (
            f"{user_id}:{request.scene}:{request.style or ''}:{request.weather or ''}:"
            f"{request.formality or ''}:{request.comfort or ''}:"
            f"{','.join(str(item_id) for item_id in request.required_item_ids)}:"
            f"{','.join(str(item_id) for item_id in request.exclude_item_ids)}:"
            f"{','.join(str(plan.id) for plan in plans)}"
        ),
    )


def _degraded_drafts(drafts: OutfitPlanSet, reason: str) -> OutfitPlanSet:
    return OutfitPlanSet(
        request_id=drafts.request_id,
        plans=drafts.plans,
        degraded=True,
        degradation_reason=reason,
        explanation_state="rule_ranked",
    )


def _role_label(role: OutfitCategory) -> str:
    return {
        OutfitCategory.TOP: "上衣",
        OutfitCategory.BOTTOM: "下装",
        OutfitCategory.DRESS: "连衣裙",
        OutfitCategory.OUTERWEAR: "外套",
        OutfitCategory.SHOES: "鞋履",
        OutfitCategory.ACCESSORY: "配饰",
    }[role]


def _build_plans(
    items: tuple[WardrobeItem, ...],
    request: OutfitRequest,
) -> tuple[OutfitPlan, ...]:
    grouped = {category: _rank_items(items, category, request) for category in OutfitCategory}
    required_by_category = {
        _category(item): item for item in items if item.id in request.required_item_ids
    }
    required_categories = frozenset(
        category for category in required_by_category if category is not None
    )
    compatible_templates = tuple(
        template
        for template in TEMPLATES
        if required_categories.issubset(template)
        and not (
            OutfitCategory.DRESS in required_categories
            and (OutfitCategory.TOP in template or OutfitCategory.BOTTOM in template)
        )
        and not (
            OutfitCategory.DRESS in template
            and (
                OutfitCategory.TOP in required_categories
                or OutfitCategory.BOTTOM in required_categories
            )
        )
    )
    # Hot weather should not force an outer layer. Six of the eight templates
    # carry OUTERWEAR, so without this nearly every plan gained a coat, and on
    # a real wardrobe that showed up as the same knit cardigan in every single
    # recommendation - even at "炎热高温".
    #
    # Only drop them when four distinct plans still remain: a small wardrobe
    # would otherwise collapse from four suggestions to one. An explicitly
    # required coat is left alone.
    if _is_hot(request.weather) and OutfitCategory.OUTERWEAR not in required_categories:
        without_outerwear = tuple(
            template
            for template in compatible_templates
            if OutfitCategory.OUTERWEAR not in template
        )
        # Keep the variety when there is not enough left without a coat.
        if len(without_outerwear) >= 4:
            compatible_templates = without_outerwear
    if not compatible_templates:
        raise OutfitPlanInvalidError("必须使用的单品无法组成不冲突的完整穿搭")
    if OutfitCategory.DRESS in required_categories:
        templates = tuple(
            template for template in compatible_templates if OutfitCategory.DRESS in template
        )
    elif {
        OutfitCategory.TOP,
        OutfitCategory.BOTTOM,
    } & required_categories:
        templates = tuple(
            template for template in compatible_templates if OutfitCategory.DRESS not in template
        )
    else:
        templates = tuple(
            sorted(
                compatible_templates,
                key=lambda template: (
                    -sum(bool(grouped[category]) for category in template),
                    sum(not grouped[category] for category in template),
                    tuple(category.value for category in template),
                ),
            )
        )
    plans: list[OutfitPlan] = []
    seen_structures: set[tuple[str, ...]] = set()
    for variant_index in range(64):
        for template in templates:
            slots = _build_template_slots(
                template=template,
                grouped=grouped,
                required_by_category=required_by_category,
                request=request,
                # Do not let the first four templates all reuse candidate zero.
                # Rotating by the number of accepted plans makes the progressive
                # cards visibly different while preserving deterministic output.
                variant_index=variant_index + len(plans),
            )
            structure = _structure_signature(slots)
            if structure in seen_structures:
                continue
            seen_structures.add(structure)
            plan_index = len(plans)
            signature = _slot_signature(slots)
            owned_count = sum(slot.ownership == OwnershipState.OWNED.value for slot in slots)
            missing = sum(slot.item_id is None for slot in slots)
            title = ("衣橱优先" if missing == 0 else "衣橱补齐") + f"方案 {plan_index + 1}"
            style_label = request.style or "协调"
            plans.append(
                OutfitPlan(
                    id=uuid5(PLAN_NAMESPACE, "|".join(signature)),
                    title=title,
                    scene=request.scene,
                    slots=slots,
                    rationale=(
                        f"围绕「{request.scene}」安排层次, 以{style_label}为主线; "
                        f"{owned_count} 件来自你已拥有的衣服"
                        + (
                            f", 另有 {missing} 个缺口给出搜索方向."
                            if missing
                            else ", 无需新增购买."
                        )
                    ),
                    style_match_score=max(62, 92 - plan_index * 4 - missing * 3),
                )
            )
            if len(plans) == 4:
                return tuple(plans)
    raise OutfitPlanInvalidError("当前衣橱不足以生成 4 套结构有差异的合法穿搭")


def _build_template_slots(
    *,
    template: tuple[OutfitCategory, ...],
    grouped: dict[OutfitCategory, tuple[WardrobeItem, ...]],
    required_by_category: dict[OutfitCategory | None, WardrobeItem],
    request: OutfitRequest,
    variant_index: int,
) -> tuple[OutfitSlot, ...]:
    slots: list[OutfitSlot] = []
    divisor = 1
    for category in template:
        required = required_by_category.get(category)
        candidates = grouped[category]
        if required is not None:
            chosen = required
        elif candidates:
            chosen = candidates[(variant_index // divisor) % len(candidates)]
            divisor *= len(candidates)
        else:
            chosen = None
        slots.append(
            _item_slot(category, chosen) if chosen is not None else _missing_slot(category, request)
        )
    return tuple(slots)


def _rank_items(
    items: Iterable[WardrobeItem],
    category: OutfitCategory,
    request: OutfitRequest,
) -> tuple[WardrobeItem, ...]:
    ordered_items = tuple(items)
    recall_position = {item.id: index for index, item in enumerate(ordered_items)}
    candidates = [
        item
        for item in ordered_items
        if _category(item) is category
        and item.id not in request.exclude_item_ids
        and _hard_compatible(item, request)
    ]
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                -_relevance(item, request),
                recall_position[item.id],
                item.created_at,
                str(item.id),
            ),
        )
    )


def _relevance(item: WardrobeItem, request: OutfitRequest) -> int:
    score = 8 if item.ownership is OwnershipState.OWNED else 5
    text = " ".join(
        str(field.value) for field in item.attributes.fields.values() if field.value is not None
    ).lower()
    for term in _query_terms(request):
        if term in text:
            score += 3
    if request.anchor_item_id == item.id:
        score += 100
    return score


def _query_terms(request: OutfitRequest) -> tuple[str, ...]:
    values = (
        request.scene,
        request.style or "",
        request.weather or "",
        request.formality or "",
        request.comfort or "",
    )
    terms: list[str] = []
    for raw_value in values:
        normalized = raw_value.strip().lower()
        if not normalized:
            continue
        terms.extend(
            part
            for part in re.split(r"[\s,，、;；。.!！？/]+", normalized)  # noqa: RUF001
            if part
        )
        for trigger, related in QUERY_CONCEPTS:
            if trigger in normalized:
                terms.extend(related)
    return tuple(dict.fromkeys(terms))


def _category(item: WardrobeItem) -> OutfitCategory | None:
    field = item.attributes.fields.get("category")
    value = str(field.value) if field is not None else ""
    if value in ACCESSORY_CATEGORIES:
        return OutfitCategory.ACCESSORY
    try:
        return OutfitCategory(value)
    except ValueError:
        return None


def _item_name(item: WardrobeItem) -> str:
    for field_name in ("description", "subcategory", "category"):
        field = item.attributes.fields.get(field_name)
        if field is not None and str(field.value).strip():
            return str(field.value).strip()
    return "衣橱单品"


def _item_slot(category: OutfitCategory, item: WardrobeItem) -> OutfitSlot:
    return OutfitSlot(
        role=category,
        item_id=item.id,
        item_name=_item_name(item),
        ownership=item.ownership.value,
        image_url=f"/v1/items/{item.id}/image",
        search_query=None,
        source_kind=item.source_kind.value,
    )


def _slot_signature(slots: tuple[OutfitSlot, ...]) -> tuple[str, ...]:
    return tuple(
        str(slot.item_id)
        if slot.item_id is not None
        else f"missing:{slot.role.value}:{slot.search_query}"
        for slot in slots
    )


def _structure_signature(slots: tuple[OutfitSlot, ...]) -> tuple[str, ...]:
    return tuple(
        f"{slot.role.value}:{slot.item_id if slot.item_id is not None else 'missing'}"
        for slot in slots
    )


def _validate_plan_hard_rules(
    plans: tuple[OutfitPlan, ...],
    *,
    request: OutfitRequest,
    items: tuple[WardrobeItem, ...],
) -> None:
    if len(plans) != 4:
        raise OutfitPlanInvalidError("每次必须生成 4 套合法穿搭")
    if len({plan.structure_signature for plan in plans}) != 4:
        raise OutfitPlanInvalidError("4 套穿搭必须在结构或真实单品上有明确差异")
    by_id = {item.id: item for item in items}
    required = set(request.required_item_ids)
    excluded = set(request.exclude_item_ids)
    for plan in plans:
        if plan.scene != request.scene:
            raise OutfitPlanInvalidError("穿搭场景与请求不一致")
        roles = tuple(slot.role for slot in plan.slots)
        if len(set(roles)) != len(roles):
            raise OutfitPlanInvalidError("一套穿搭不能重复同一位置")
        if OutfitCategory.DRESS in roles and (
            OutfitCategory.TOP in roles or OutfitCategory.BOTTOM in roles
        ):
            raise OutfitPlanInvalidError("连衣裙不能与上衣或下装同时作为主穿搭")
        plan_item_ids = set(plan.wardrobe_item_ids)
        if not required.issubset(plan_item_ids) or plan_item_ids & excluded:
            raise OutfitPlanInvalidError("穿搭没有遵守必选或排除单品")
        if len(plan_item_ids) != len(plan.wardrobe_item_ids):
            raise OutfitPlanInvalidError("一套穿搭不能重复使用同一件单品")
        for slot in plan.slots:
            if slot.item_id is None:
                continue
            item = by_id.get(slot.item_id)
            if (
                item is None
                or item.status not in {ItemStatus.READY, ItemStatus.PARTIAL}
                or _category(item) is not slot.role
                or not _hard_compatible(item, request)
            ):
                raise OutfitPlanInvalidError("穿搭包含不合法或不兼容的单品")


def _validate_reranked_plans(
    drafts: tuple[OutfitPlan, ...],
    reranked: tuple[OutfitPlan, ...],
) -> None:
    if len(reranked) != 4 or len({plan.id for plan in reranked}) != 4:
        raise OutfitPlanInvalidError("重排必须原样返回 4 套候选")
    draft_by_id = {plan.id: plan for plan in drafts}
    if set(draft_by_id) != {plan.id for plan in reranked}:
        raise OutfitPlanInvalidError("重排不能新增、删除或替换穿搭候选")
    for plan in reranked:
        draft = draft_by_id[plan.id]
        if (
            plan.scene != draft.scene
            or plan.slots != draft.slots
            or plan.title != draft.title
            or plan.structure_signature != draft.structure_signature
        ):
            raise OutfitPlanInvalidError("重排只能调整候选顺序、理由和分数")


def _recall_requirements(
    request: OutfitRequest,
    *,
    required_roles: tuple[OutfitCategory, ...],
    anchor_item_id: UUID | None = None,
    additional_exclusions: tuple[UUID, ...] = (),
) -> OutfitRecallRequirements:
    exclusions = tuple(dict.fromkeys((*request.exclude_item_ids, *additional_exclusions)))
    anchor = request.anchor_item_id if anchor_item_id is None else anchor_item_id
    return OutfitRecallRequirements(
        scene=request.scene,
        weather=request.weather,
        formality=request.formality,
        season=_season_hint(request.weather),
        exclude_item_ids=exclusions,
        required_roles=required_roles,
        anchor_item_id=anchor,
    )


def _season_hint(weather: str | None) -> str | None:
    value = (weather or "").lower()
    if any(token in value for token in ("炎热", "高温", "盛夏", "闷热", "夏")):
        return "夏季"
    if any(token in value for token in ("寒冷", "低温", "下雪", "冬")):
        return "冬季"
    if any(token in value for token in ("春", "温暖")):
        return "春季"
    if any(token in value for token in ("秋", "凉爽")):
        return "秋季"
    return None


def _validate_required_items(
    items: tuple[WardrobeItem, ...],
    request: OutfitRequest,
) -> None:
    categories = [_category(item) for item in items]
    if len(categories) != len(set(categories)):
        raise OutfitPlanInvalidError("每个搭配位置只能指定一件必选单品")
    if OutfitCategory.DRESS in categories and (
        OutfitCategory.TOP in categories or OutfitCategory.BOTTOM in categories
    ):
        raise OutfitPlanInvalidError("连衣裙不能与必选上衣或下装同时组成主穿搭")
    incompatible = [item for item in items if not _hard_compatible(item, request)]
    if incompatible:
        raise OutfitPlanInvalidError("必选单品与天气或正式度要求明显冲突")


def _attribute_text(item: WardrobeItem) -> str:
    return " ".join(
        str(field.value) for field in item.attributes.fields.values() if field.value is not None
    ).lower()



def _is_hot(weather: str | None) -> bool:
    return any(
        token in (weather or "").lower()
        for token in ("炎热", "高温", "盛夏", "闷热")
    )


def _hard_compatible(item: WardrobeItem, request: OutfitRequest) -> bool:
    text = _attribute_text(item)
    weather = (request.weather or "").lower()
    formality = (request.formality or "").lower()
    comfort = (request.comfort or "").lower()
    if any(token in weather for token in ("炎热", "高温", "盛夏", "闷热")) and any(
        token in text for token in ("秋冬", "厚重", "羽绒", "羊毛大衣")
    ):
        return False
    if any(token in weather for token in ("寒冷", "低温", "下雪", "冬季")) and any(
        token in text for token in ("夏日", "吊带", "背心", "凉鞋")
    ):
        return False
    if any(token in comfort for token in ("久走", "步行", "站立", "舒适")) and any(
        token in text for token in ("超高跟", "紧身束缚", "硬底")
    ):
        return False
    return not (
        any(token in formality for token in ("正式", "商务", "面试", "礼服"))
        and any(token in text for token in ("沙滩", "居家", "睡衣", "运动"))
    )


def _missing_slot(
    category: OutfitCategory,
    request: OutfitRequest,
) -> OutfitSlot:
    names = {
        OutfitCategory.TOP: "上衣",
        OutfitCategory.BOTTOM: "下装",
        OutfitCategory.DRESS: "连衣裙",
        OutfitCategory.OUTERWEAR: "外套",
        OutfitCategory.SHOES: "鞋",
        OutfitCategory.ACCESSORY: "配饰",
    }
    return OutfitSlot(
        role=category,
        item_id=None,
        item_name=None,
        ownership=None,
        image_url=None,
        search_query=f"{request.style or request.scene} {names[category]}",
        source_kind=None,
    )
