from __future__ import annotations

import logging
from collections.abc import Iterable
from uuid import UUID, uuid5

from stylecapture_backend.features.capture.domain import OwnershipState
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitPlanSet,
    OutfitRequest,
    OutfitSlot,
)
from stylecapture_backend.features.outfit.ports import OutfitReranker, OutfitWardrobeReader
from stylecapture_backend.features.wardrobe.domain import ItemStatus, WardrobeItem

PLAN_NAMESPACE = UUID("7fb45e4c-8de2-48d2-9652-ec5463a42e65")
logger = logging.getLogger(__name__)

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
)

ACCESSORY_CATEGORIES = {"bags", "headwear", "accessories"}


class OutfitWardrobeEmptyError(ValueError):
    """The user has no ready wardrobe assets that can form a plan."""


class OutfitApplication:
    def __init__(
        self,
        *,
        wardrobe: OutfitWardrobeReader,
        reranker: OutfitReranker | None,
    ) -> None:
        self._wardrobe = wardrobe
        self._reranker = reranker

    async def plan(
        self,
        *,
        user_id: UUID,
        request: OutfitRequest,
    ) -> OutfitPlanSet:
        items = tuple(
            item
            for item in await self._wardrobe.list_for_user(user_id)
            if item.status in {ItemStatus.READY, ItemStatus.PARTIAL} and _category(item) is not None
        )
        if not items:
            raise OutfitWardrobeEmptyError("请先保存至少一件已识别的真实衣服")
        plans = _build_plans(items, request)
        if self._reranker is None:
            return OutfitPlanSet.rule_ranked(
                plans,
                degradation_reason="reasoning_not_configured",
            )
        try:
            ranked = await self._reranker.rerank(request, plans)
        except Exception as exc:
            logger.warning(
                "Outfit reasoning degraded safely (%s)",
                type(exc).__name__,
            )
            return OutfitPlanSet.rule_ranked(
                plans,
                degradation_reason="reasoning_temporarily_unavailable",
            )
        return OutfitPlanSet(
            request_id=uuid5(
                PLAN_NAMESPACE,
                f"{user_id}:{request.scene}:{request.style or ''}:{','.join(str(p.id) for p in ranked)}",
            ),
            plans=ranked,
            degraded=False,
            degradation_reason=None,
            explanation_state="llm_ranked",
        )


def _build_plans(
    items: tuple[WardrobeItem, ...],
    request: OutfitRequest,
) -> tuple[OutfitPlan, ...]:
    grouped = {category: _rank_items(items, category, request) for category in OutfitCategory}
    plans: list[OutfitPlan] = []
    signatures: set[tuple[str, ...]] = set()
    for plan_index, preferred_template in enumerate(TEMPLATES):
        template = (
            preferred_template
            if any(grouped[category] for category in preferred_template)
            else TEMPLATES[plan_index % len(TEMPLATES)]
        )
        if not any(grouped[category] for category in template):
            template = TEMPLATES[0]
        slots: list[OutfitSlot] = []
        for category in template:
            candidates = grouped[category]
            chosen = candidates[plan_index % len(candidates)] if candidates else None
            slots.append(
                _item_slot(category, chosen)
                if chosen is not None
                else _missing_slot(category, request, plan_index=plan_index)
            )
        signature = tuple(
            str(slot.item_id) if slot.item_id is not None else f"missing:{slot.role.value}"
            for slot in slots
        )
        if signature in signatures:
            signature = (*signature, f"variant:{plan_index}")
        signatures.add(signature)
        owned_count = sum(slot.ownership == OwnershipState.OWNED.value for slot in slots)
        missing = sum(slot.item_id is None for slot in slots)
        title = ("衣橱优先" if missing == 0 else "衣橱补齐") + f"方案 {plan_index + 1}"
        style_label = request.style or "协调"
        plans.append(
            OutfitPlan(
                id=uuid5(PLAN_NAMESPACE, "|".join(signature)),
                title=title,
                scene=request.scene,
                slots=tuple(slots),
                rationale=(
                    f"围绕「{request.scene}」安排层次, 以{style_label}为主线; "
                    f"{owned_count} 件来自你已拥有的衣服"
                    + (f", 另有 {missing} 个缺口给出搜索方向." if missing else ", 无需新增购买.")
                ),
                style_match_score=max(62, 92 - plan_index * 4 - missing * 3),
            )
        )
    return tuple(plans)


def _rank_items(
    items: Iterable[WardrobeItem],
    category: OutfitCategory,
    request: OutfitRequest,
) -> tuple[WardrobeItem, ...]:
    candidates = [item for item in items if _category(item) is category]
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                -_relevance(item, request),
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
    for token in (request.scene, request.style or "", request.weather or "", request.comfort or ""):
        for part in token.lower().split():
            if part and part in text:
                score += 3
    if request.anchor_item_id == item.id:
        score += 100
    return score


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
    )


def _missing_slot(
    category: OutfitCategory,
    request: OutfitRequest,
    *,
    plan_index: int,
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
        search_query=f"{request.style or request.scene} {names[category]} 方案{plan_index + 1}",
    )
