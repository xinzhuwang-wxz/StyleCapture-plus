from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitRequest,
    OutfitSlot,
)
from stylecapture_backend.features.outfit.infrastructure.reranker import (
    OUTFIT_RERANK_MODEL_VERSION,
    OUTFIT_RERANK_PROMPT_VERSION,
    OUTFIT_RERANK_SCHEMA_VERSION,
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
async def test_litellm_reranker_receives_wardrobe_style_facts() -> None:
    calls: list[dict[str, Any]] = []

    async def completion(**kwargs: object) -> object:
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"rankedPlans":['
                            '{"id":"00000000-0000-0000-0000-000000000001",'
                            '"rationale":"浅绿针织和灰裙色彩柔和且层次成立",'
                            '"styleMatchScore":94}]}'
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
    slot = OutfitSlot(
        role=OutfitCategory.OUTERWEAR,
        item_id=UUID("00000000-0000-0000-0000-000000000010"),
        item_name="浅绿圆领针织开衫",
        ownership="owned",
        image_url="/v1/items/10/image",
        search_query=None,
        style_facts={
            "colors": ["浅绿", "薄荷绿"],
            "materials": ["针织", "棉混纺"],
            "pattern": "纯色",
            "silhouette": "短款直筒",
            "fit": "合身",
            "styles": ["温柔", "学院", "清新", "叠穿"],
            "seasons": ["春", "秋"],
            "occasions": ["日常", "约会"],
            "length": "短款",
            "neckline": "圆领",
            "sleeve_type": "长袖",
            "details": ["纽扣", "罗纹边"],
        },
    )
    await reranker.rerank(
        OutfitRequest(scene="周末约会", style="温柔有层次"),
        (
            OutfitPlan(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                title="衣橱优先方案",
                scene="周末约会",
                slots=(
                    slot,
                    OutfitSlot(
                        role=OutfitCategory.BOTTOM,
                        item_id=UUID("00000000-0000-0000-0000-000000000011"),
                        item_name="灰色半身长裙",
                        ownership="owned",
                        image_url="/v1/items/11/image",
                        search_query=None,
                    ),
                    OutfitSlot(
                        role=OutfitCategory.SHOES,
                        item_id=UUID("00000000-0000-0000-0000-000000000012"),
                        item_name="白色厚底运动鞋",
                        ownership="owned",
                        image_url="/v1/items/12/image",
                        search_query=None,
                    ),
                ),
                rationale="规则排序说明",
                style_match_score=88,
            ),
        ),
    )

    payload = json.loads(calls[0]["messages"][1]["content"])
    outerwear = payload["candidates"][0]["slots"][0]
    assert outerwear["style_facts"] == {
        "colors": ["浅绿", "薄荷绿"],
        "materials": ["针织", "棉混纺"],
        "pattern": "纯色",
        "silhouette": "短款直筒",
        "fit": "合身",
        "styles": ["温柔", "学院", "清新", "叠穿"],
        "seasons": ["春", "秋"],
        "occasions": ["日常", "约会"],
        "length": "短款",
        "neckline": "圆领",
        "sleeve_type": "长袖",
        "details": ["纽扣", "罗纹边"],
    }


@pytest.mark.asyncio
async def test_litellm_reranker_only_reorders_closed_candidates() -> None:
    calls: list[dict[str, Any]] = []

    async def completion(**kwargs: object) -> object:
        calls.append(kwargs)
        return SimpleNamespace(
            model="raw-provider-endpoint-must-not-leak",
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
            ],
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

    assert [str(candidate.id) for candidate in result.plans] == [
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000001",
    ]
    assert result.plans[0].rationale == "深色层次更符合正式通勤场景"
    assert result.trace.capability_alias == "reasoning"
    assert result.trace.model_version == OUTFIT_RERANK_MODEL_VERSION
    assert result.trace.prompt_version == OUTFIT_RERANK_PROMPT_VERSION
    assert result.trace.schema_version == OUTFIT_RERANK_SCHEMA_VERSION
    assert "raw-provider-endpoint" not in repr(result.trace)
    assert result.trace.latency_ms >= 1
    assert calls[0]["model"] == "openai/reasoning"
    assert calls[0]["api_base"] == "http://litellm:4000/v1"
    assert "server-only-test-key" not in str(calls[0]["messages"])
    messages = calls[0]["messages"]
    assert "视觉重量与廓形平衡" in messages[0]["content"]
    assert "减少不同方案重复使用同一件衣服" in messages[0]["content"]
    assert json.loads(messages[1]["content"])["request"]["outfit_count"] == 4


def test_litellm_reranker_requires_a_capability_alias() -> None:
    with pytest.raises(ValueError, match="capability alias"):
        LiteLLMOutfitReranker(
            capability_alias=" ",
            gateway_base_url="http://litellm:4000/v1",
            gateway_api_key="server-only-test-key",
        )


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
