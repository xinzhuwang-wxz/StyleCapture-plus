from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.domain import CaptureSourceKind, OwnershipState
from stylecapture_backend.features.outfit.application import OutfitApplication
from stylecapture_backend.features.outfit.domain import OutfitPlan, OutfitRequest
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

    async def list_for_user(self, user_id: UUID) -> list[WardrobeItem]:
        return [item for item in self.items if item.user_id == user_id]


class ChineseReranker:
    async def rerank(
        self,
        request: OutfitRequest,
        plans: tuple[OutfitPlan, ...],
    ) -> tuple[OutfitPlan, ...]:
        return tuple(
            plan.with_ranking(
                rationale=f"{request.scene}下强调真实衣橱的色彩与层次关系",
                score=95 - index,
            )
            for index, plan in enumerate(reversed(plans))
        )


def item(
    user_id: UUID,
    *,
    category: str,
    description: str,
    ownership: OwnershipState = OwnershipState.OWNED,
) -> WardrobeItem:
    now = datetime.now(UTC)
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
        attributes=ItemAttributes(
            {
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
        ),
        model_metadata={},
        embedding=None,
        created_at=now,
        updated_at=now,
    )


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
