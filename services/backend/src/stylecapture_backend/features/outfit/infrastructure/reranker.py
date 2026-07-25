from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any, cast

from litellm import acompletion

from stylecapture_backend.features.outfit.domain import (
    OutfitPlan,
    OutfitReasoningTrace,
    OutfitRequest,
    OutfitRerankResult,
)

CompletionCall = Callable[..., Awaitable[object]]

OUTFIT_RERANK_MODEL_VERSION = "outfit-rerank-model-v1"
OUTFIT_RERANK_PROMPT_VERSION = "outfit-rerank-v1"
OUTFIT_RERANK_SCHEMA_VERSION = "outfit-rerank-json-v1"


class LiteLLMOutfitReranker:
    def __init__(
        self,
        *,
        capability_alias: str,
        gateway_base_url: str,
        gateway_api_key: str,
        completion: CompletionCall = acompletion,
        timeout_seconds: float = 30,
    ) -> None:
        if not capability_alias.strip():
            raise ValueError("outfit reranking capability alias must not be empty")
        self._alias = capability_alias.strip()
        self._base_url = gateway_base_url.rstrip("/")
        self._api_key = gateway_api_key
        self._completion = completion
        self._timeout_seconds = timeout_seconds

    async def rerank(
        self,
        request: OutfitRequest,
        plans: tuple[OutfitPlan, ...],
    ) -> OutfitRerankResult:
        closed_candidates = [
            {
                "id": str(plan.id),
                "rationale": plan.rationale,
                "score": plan.style_match_score,
                "slots": [
                    {
                        "role": slot.role.value,
                        "item_name": slot.item_name,
                        "ownership": slot.ownership,
                        "missing_search": slot.search_query,
                    }
                    for slot in plan.slots
                ],
            }
            for plan in plans
        ]
        started = monotonic()
        async with asyncio.timeout(self._timeout_seconds):
            response = await self._completion(
                model=f"openai/{self._alias}",
                api_base=self._base_url,
                api_key=self._api_key,
                temperature=0.2,
                max_tokens=700,
                num_retries=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "重排给定穿搭候选并写简洁中文理由。不得改变单品。严格返回 JSON:"
                            '{"rankedPlans":[{"id":string,"rationale":string,'
                            '"styleMatchScore":0..100}]}。理由不超过50字。'
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "request": {
                                    "scene": request.scene,
                                    "style": request.style,
                                    "weather": request.weather,
                                    "formality": request.formality,
                                    "comfort": request.comfort,
                                },
                                "candidates": closed_candidates,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
        content = cast(Any, response).choices[0].message.content
        payload = json.loads(content)
        rankings = payload["rankedPlans"]
        by_id = {str(plan.id): plan for plan in plans}
        if not isinstance(rankings, list) or len(rankings) != len(plans):
            raise ValueError("reranker returned an invalid plan count")
        output: list[OutfitPlan] = []
        seen: set[str] = set()
        for ranking in rankings:
            plan_id = str(ranking["id"])
            if plan_id in seen or plan_id not in by_id:
                raise ValueError("reranker returned an unknown or duplicate plan")
            rationale = str(ranking["rationale"]).strip()
            score = int(ranking["styleMatchScore"])
            if len(rationale) < 8 or not 0 <= score <= 100:
                raise ValueError("reranker returned invalid fields")
            seen.add(plan_id)
            output.append(by_id[plan_id].with_ranking(rationale=rationale, score=score))
        return OutfitRerankResult(
            plans=tuple(output),
            trace=OutfitReasoningTrace(
                capability_alias=self._alias,
                model_version=OUTFIT_RERANK_MODEL_VERSION,
                prompt_version=OUTFIT_RERANK_PROMPT_VERSION,
                schema_version=OUTFIT_RERANK_SCHEMA_VERSION,
                latency_ms=max(1, round((monotonic() - started) * 1000)),
            ),
        )
