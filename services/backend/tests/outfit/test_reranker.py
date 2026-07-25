from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitRequest,
    OutfitSlot,
)
from stylecapture_backend.features.outfit.infrastructure.reranker import (
    LiteLLMOutfitReranker,
)


def plan(plan_id: str, *, score: int) -> OutfitPlan:
    slots = tuple(
        OutfitSlot(
            role=role,
            item_id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
            item_name=name,
            ownership="owned",
            image_url=f"/v1/items/{index}/image",
            search_query=None,
        )
        for index, (role, name) in enumerate(
            (
                (OutfitCategory.TOP, "白色针织衫"),
                (OutfitCategory.BOTTOM, "黑色西裤"),
                (OutfitCategory.SHOES, "黑色皮鞋"),
            ),
            start=10,
        )
    )
    return OutfitPlan(
        id=UUID(plan_id),
        title="衣橱优先方案",
        scene="通勤面试",
        slots=slots,
        rationale="规则排序说明",
        style_match_score=score,
    )


@pytest.mark.asyncio
async def test_litellm_reranker_only_reorders_closed_candidates() -> None:
    calls: list[dict[str, object]] = []

    async def completion(**kwargs: object) -> object:
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"rankedPlans":['
                            '{"id":"00000000-0000-0000-0000-000000000002",'
                            '"rationale":"深色层次更符合正式通勤场景","styleMatchScore":96},'
                            '{"id":"00000000-0000-0000-0000-000000000001",'
                            '"rationale":"浅色组合柔和但正式感略弱","styleMatchScore":86}]}'
                        )
                    )
                )
            ]
        )

    reranker = LiteLLMOutfitReranker(
        capability_alias="reasoning",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="server-only-test-key",
        completion=completion,
    )

    result = await reranker.rerank(
        OutfitRequest(scene="通勤面试", style="利落不刻板"),
        (
            plan("00000000-0000-0000-0000-000000000001", score=90),
            plan("00000000-0000-0000-0000-000000000002", score=80),
        ),
    )

    assert [str(candidate.id) for candidate in result] == [
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000001",
    ]
    assert result[0].rationale == "深色层次更符合正式通勤场景"
    assert calls[0]["model"] == "openai/reasoning"
    assert calls[0]["api_base"] == "http://litellm:4000/v1"
    assert "server-only-test-key" not in str(calls[0]["messages"])


@pytest.mark.asyncio
async def test_litellm_reranker_rejects_unknown_candidate() -> None:
    async def completion(**_: object) -> object:
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"rankedPlans":['
                            '{"id":"00000000-0000-0000-0000-000000000099",'
                            '"rationale":"不存在的候选不应进入结果","styleMatchScore":99}]}'
                        )
                    )
                )
            ]
        )

    reranker = LiteLLMOutfitReranker(
        capability_alias="reasoning",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="server-only-test-key",
        completion=completion,
    )

    with pytest.raises(ValueError, match="unknown or duplicate"):
        await reranker.rerank(
            OutfitRequest(scene="通勤面试"),
            (plan("00000000-0000-0000-0000-000000000001", score=90),),
        )
