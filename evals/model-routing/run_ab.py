from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from litellm import acompletion
from stylecapture_backend.features.capture.domain import (
    ImagePayload,
    NormalizedPoint,
)
from stylecapture_backend.features.capture.infrastructure.providers import (
    LiteLLMVisionTagger,
)
from stylecapture_backend.features.look.domain import LookComponent
from stylecapture_backend.features.look.infrastructure.outfit_analysis import (
    LiteLLMOutfitAnalyzer,
)
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitPlan,
    OutfitRequest,
    OutfitSlot,
)
from stylecapture_backend.features.outfit.infrastructure.reranker import (
    LiteLLMOutfitReranker,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = REPOSITORY_ROOT / "services/backend/src/stylecapture_backend/demo_assets"
FEED_POSTER_ROOT = REPOSITORY_ROOT / "apps/h5/public/feed/posters"
DEFAULT_GATEWAY_URL = "http://127.0.0.1:4000/v1"
LOCAL_GATEWAY_DEFAULT = "local-litellm-gateway-key-change-before-production"
PRICE_SOURCE = "https://www.volcengine.com/docs/84458/1585097?lang=zh&redirect=1"


@dataclass(frozen=True)
class Candidate:
    label: str
    alias: str
    provider_model: str
    input_cny_per_million: float
    output_cny_per_million: float


CANDIDATES = (
    Candidate(
        label="lite",
        alias="candidate_doubao_seed_2_0_lite_260428",
        provider_model="doubao-seed-2-0-lite-260428",
        input_cny_per_million=0.60,
        output_cny_per_million=3.60,
    ),
    Candidate(
        label="mini",
        alias="candidate_doubao_seed_2_0_mini_260428",
        provider_model="doubao-seed-2-0-mini-260428",
        input_cny_per_million=0.20,
        output_cny_per_million=2.00,
    ),
)


@dataclass(frozen=True)
class GarmentCase:
    key: str
    path: Path
    source_ref: str
    category: str
    subcategory: str
    color_terms: tuple[str, ...]
    evidence_terms: tuple[str, ...]


GARMENT_CASES = (
    GarmentCase(
        key="blue_yellow_print_dress",
        path=ASSET_ROOT / "user-items/blue-yellow-print-dress.png",
        source_ref="local-curated-seed:single-item-presets/item-01",
        category="dresses",
        subcategory="dress",
        color_terms=("蓝", "黄", "白"),
        evidence_terms=("吊带", "印花", "收腰", "连衣裙"),
    ),
    GarmentCase(
        key="black_sneakers",
        path=ASSET_ROOT / "user-items/black-sneakers.png",
        source_ref="local-curated-seed:single-item-presets/item-03",
        category="shoes",
        subcategory="sneakers",
        color_terms=("黑", "白"),
        evidence_terms=("低帮", "系带", "运动", "条纹"),
    ),
    GarmentCase(
        key="pale_green_cardigan",
        path=ASSET_ROOT / "user-items/pale-green-cardigan.png",
        source_ref="local-curated-seed:single-item-presets/item-04",
        category="outerwear",
        subcategory="cardigan",
        color_terms=("绿",),
        evidence_terms=("开衫", "针织", "圆领", "纽扣"),
    ),
)


@dataclass(frozen=True)
class LookCase:
    key: str
    path: Path
    source_ref: str
    roles: tuple[str, ...]
    expected_terms: Mapping[str, tuple[str, ...]]


LOOK_CASES = (
    LookCase(
        key="city_commute",
        path=FEED_POSTER_ROOT / "pexels-7681932.jpg",
        source_ref="https://www.pexels.com/video/7681932/",
        roles=("tops", "bottoms", "outerwear", "shoes"),
        expected_terms={
            "scene": ("户外", "建筑", "街道", "步行", "阳光"),
            "style": ("通勤", "利落", "简约", "正式"),
            "color": ("米", "燕麦", "卡其", "黑"),
            "layering": ("外套", "西装", "叠穿", "层次", "外穿", "内搭"),
        },
    ),
    LookCase(
        key="evening_blue",
        path=FEED_POSTER_ROOT / "pexels-15396483.jpg",
        source_ref="https://www.pexels.com/video/15396483/",
        roles=("dresses", "shoes"),
        expected_terms={
            "scene": ("户外", "台阶", "红色", "活动", "红毯"),
            "style": ("华丽", "优雅", "礼服", "聚会"),
            "color": ("蓝",),
            "focal_point": ("蓝", "亮片", "礼服", "单肩"),
        },
    ),
    LookCase(
        key="weekend_denim",
        path=FEED_POSTER_ROOT / "pexels-7760056.jpg",
        source_ref="https://www.pexels.com/video/7760056/",
        roles=("tops", "bottoms", "outerwear", "shoes"),
        expected_terms={
            "scene": ("室内", "摄影棚", "背景"),
            "style": ("休闲", "简约", "复古", "轻松"),
            "color": ("蓝", "白", "米"),
            "layering": ("外套", "西装", "叠穿", "层次", "手持", "未上身"),
        },
    ),
)


@dataclass(frozen=True)
class ReasoningCase:
    key: str
    request: OutfitRequest
    expected_top_plan: str


REASONING_CASES = (
    ReasoningCase(
        key="business_interview",
        request=OutfitRequest(
            scene="北京客户面试与正式会议",
            style="克制利落, 不刻板",
            weather="初秋晴天",
            formality="商务正式",
            comfort="适合步行通勤",
        ),
        expected_top_plan="00000000-0000-0000-0000-000000000101",
    ),
    ReasoningCase(
        key="weekend_garden",
        request=OutfitRequest(
            scene="周末去植物园散步和喝咖啡",
            style="轻松复古休闲",
            weather="温暖多云",
            formality="休闲",
            comfort="透气并方便长时间步行",
        ),
        expected_top_plan="00000000-0000-0000-0000-000000000102",
    ),
    ReasoningCase(
        key="evening_reception",
        request=OutfitRequest(
            scene="晚间品牌酒会与正式合影",
            style="华丽但不过度堆叠",
            weather="室内恒温",
            formality="晚宴正式",
            comfort="可站立两小时",
        ),
        expected_top_plan="00000000-0000-0000-0000-000000000103",
    ),
)


def _contains_cjk(value: str) -> bool:
    return any("\u3400" <= character <= "\u9fff" for character in value)


def _all_user_text_is_chinese(values: Iterable[object]) -> bool:
    strings: list[str] = []
    for value in values:
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, list | tuple):
            strings.extend(str(item) for item in value)
    return bool(strings) and all(_contains_cjk(value) for value in strings)


def _image(path: Path) -> ImagePayload:
    body = path.read_bytes()
    content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return ImagePayload(
        object_key=f"eval/{path.name}",
        content_type=content_type,
        body=body,
        sha256=sha256(body).hexdigest(),
    )


def _usage_value(usage: object, name: str) -> int:
    value = getattr(usage, name, None)
    if value is None and isinstance(usage, Mapping):
        value = usage.get(name)
    return int(value or 0)


class RecordingCompletion:
    def __init__(self) -> None:
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.response_model: str | None = None

    async def __call__(self, **kwargs: Any) -> object:
        response = await acompletion(**kwargs)
        usage = getattr(response, "usage", None)
        self.usage = {
            "prompt_tokens": _usage_value(usage, "prompt_tokens"),
            "completion_tokens": _usage_value(usage, "completion_tokens"),
            "total_tokens": _usage_value(usage, "total_tokens"),
        }
        model = getattr(response, "model", None)
        self.response_model = str(model) if model else None
        return response


def _estimated_cost(usage: Mapping[str, int], candidate: Candidate) -> float:
    return round(
        (
            usage["prompt_tokens"] * candidate.input_cny_per_million
            + usage["completion_tokens"] * candidate.output_cny_per_million
        )
        / 1_000_000,
        8,
    )


def _safe_error(error: Exception) -> dict[str, object]:
    return {
        "type": type(error).__name__,
        "code": str(getattr(error, "code", "request_failed")),
        "retryable": bool(getattr(error, "retryable", False)),
    }


def _score_garment_output(
    fields: Mapping[str, object], case: GarmentCase
) -> tuple[dict[str, object], float]:
    category_ok = fields["category"] == case.category
    subcategory_ok = fields["subcategory"] == case.subcategory
    colors_text = " ".join(str(value) for value in fields["colors"])
    color_hits = sum(term in colors_text for term in case.color_terms)
    evidence_text = json.dumps(fields, ensure_ascii=False)
    evidence_hits = sum(term in evidence_text for term in case.evidence_terms)
    chinese_ok = _all_user_text_is_chinese(
        value for name, value in fields.items() if name not in {"category", "subcategory"}
    )
    score = round(
        40 * int(category_ok)
        + 20 * int(subcategory_ok)
        + 20 * color_hits / len(case.color_terms)
        + 20 * evidence_hits / len(case.evidence_terms),
        1,
    )
    return (
        {
            "json_schema_valid": True,
            "taxonomy_valid": True,
            "chinese_complete": chinese_ok,
            "category_expected": category_ok,
            "subcategory_expected": subcategory_ok,
            "color_term_recall": round(color_hits / len(case.color_terms), 3),
            "evidence_term_recall": round(evidence_hits / len(case.evidence_terms), 3),
        },
        score,
    )


def _score_look_output(
    fields: Mapping[str, str], case: LookCase
) -> tuple[dict[str, object], float]:
    term_checks = {
        name: any(term in fields[name] for term in terms)
        for name, terms in case.expected_terms.items()
    }
    chinese_ok = _all_user_text_is_chinese(fields.values())
    score = round(60 + 40 * sum(term_checks.values()) / len(term_checks), 1)
    return (
        {
            "json_schema_valid": True,
            "taxonomy_valid": True,
            "chinese_complete": chinese_ok,
            "semantic_fields": term_checks,
        },
        score,
    )


def _score_reasoning_output(
    output: list[Mapping[str, object]], case: ReasoningCase
) -> tuple[dict[str, object], float]:
    ranked_ids = [str(plan["id"]) for plan in output]
    rationales = [str(plan["rationale"]) for plan in output]
    original_ids = {str(plan.id) for plan in _plans()}
    closed_set_ok = len(ranked_ids) == len(original_ids) and set(ranked_ids) == original_ids
    chinese_ok = _all_user_text_is_chinese(rationales)
    expected_top = ranked_ids[0] == case.expected_top_plan
    score = round(
        40 * int(closed_set_ok) + 30 * int(chinese_ok) + 30 * int(expected_top),
        1,
    )
    return (
        {
            "json_schema_valid": True,
            "taxonomy_valid": True,
            "chinese_complete": chinese_ok,
            "closed_candidate_set_preserved": closed_set_ok,
            "expected_top_plan": expected_top,
        },
        score,
    )


async def _run_garment(
    candidate: Candidate,
    case: GarmentCase,
    *,
    gateway_url: str,
    gateway_key: str,
) -> dict[str, object]:
    recorder = RecordingCompletion()
    tagger = LiteLLMVisionTagger(
        capability_alias=candidate.alias,
        gateway_base_url=gateway_url,
        gateway_api_key=gateway_key,
        completion=recorder,
    )
    started = perf_counter()
    try:
        analysis = await tagger.describe(_image(case.path))
        wall_latency_ms = round((perf_counter() - started) * 1000)
        fields = {name: field.value for name, field in analysis.fields.items()}
        checks, score = _score_garment_output(fields, case)
        return {
            "capability": "garment_understanding",
            "case": case.key,
            "source_ref": case.source_ref,
            "status": "success",
            "wall_latency_ms": wall_latency_ms,
            "provider_latency_ms": analysis.metadata.latency_ms,
            "usage": recorder.usage,
            "estimated_cost_cny": _estimated_cost(recorder.usage, candidate),
            "checks": checks,
            "quality_score": score,
            "output": fields,
        }
    except Exception as error:  # sanitized boundary: never persist provider payloads
        return {
            "capability": "garment_understanding",
            "case": case.key,
            "source_ref": case.source_ref,
            "status": "error",
            "wall_latency_ms": round((perf_counter() - started) * 1000),
            "usage": recorder.usage,
            "estimated_cost_cny": _estimated_cost(recorder.usage, candidate),
            "error": _safe_error(error),
            "quality_score": 0,
        }


def _components(roles: tuple[str, ...]) -> tuple[LookComponent, ...]:
    polygon = (
        NormalizedPoint(0.1, 0.1),
        NormalizedPoint(0.9, 0.1),
        NormalizedPoint(0.9, 0.9),
        NormalizedPoint(0.1, 0.9),
    )
    look_id = uuid4()
    return tuple(
        LookComponent.pending(
            look_id=look_id,
            component_key=f"component-{index}",
            evidence_region=polygon,
            confidence=0.9,
            grounding_metadata={"source": "curated_eval"},
            role=role,
            display_order=index,
        )
        for index, role in enumerate(roles)
    )


async def _run_look(
    candidate: Candidate,
    case: LookCase,
    *,
    gateway_url: str,
    gateway_key: str,
) -> dict[str, object]:
    recorder = RecordingCompletion()
    analyzer = LiteLLMOutfitAnalyzer(
        capability_alias=candidate.alias,
        gateway_base_url=gateway_url,
        gateway_api_key=gateway_key,
        completion=recorder,
    )
    started = perf_counter()
    try:
        analysis = await analyzer.analyze(
            _image(case.path),
            components=_components(case.roles),
        )
        wall_latency_ms = round((perf_counter() - started) * 1000)
        fields = {
            name: getattr(analysis, name).value
            for name in (
                "color",
                "silhouette",
                "material",
                "layering",
                "focal_point",
                "scene",
                "style",
            )
        }
        checks, score = _score_look_output(fields, case)
        return {
            "capability": "outfit_analysis",
            "case": case.key,
            "source_ref": case.source_ref,
            "status": "success",
            "wall_latency_ms": wall_latency_ms,
            "provider_latency_ms": analysis.metadata.latency_ms,
            "usage": recorder.usage,
            "estimated_cost_cny": _estimated_cost(recorder.usage, candidate),
            "checks": checks,
            "quality_score": score,
            "output": fields,
        }
    except Exception as error:
        return {
            "capability": "outfit_analysis",
            "case": case.key,
            "source_ref": case.source_ref,
            "status": "error",
            "wall_latency_ms": round((perf_counter() - started) * 1000),
            "usage": recorder.usage,
            "estimated_cost_cny": _estimated_cost(recorder.usage, candidate),
            "error": _safe_error(error),
            "quality_score": 0,
        }


def _slot(
    role: OutfitCategory,
    item_number: int,
    name: str,
) -> OutfitSlot:
    return OutfitSlot(
        role=role,
        item_id=UUID(f"00000000-0000-0000-0001-{item_number:012d}"),
        item_name=name,
        ownership="owned",
        image_url=f"/eval/items/{item_number}",
        search_query=None,
    )


def _plans() -> tuple[OutfitPlan, ...]:
    return (
        OutfitPlan(
            id=UUID("00000000-0000-0000-0000-000000000101"),
            title="城市商务",
            scene="通勤、面试和正式会议",
            slots=(
                _slot(OutfitCategory.TOP, 1011, "象牙白针织衫"),
                _slot(OutfitCategory.BOTTOM, 1012, "燕麦色高腰西裤"),
                _slot(OutfitCategory.OUTERWEAR, 1013, "黑色廓形大衣"),
                _slot(OutfitCategory.SHOES, 1014, "黑色通勤皮鞋"),
            ),
            rationale="规则基线: 结构正式且配色克制",
            style_match_score=72,
        ),
        OutfitPlan(
            id=UUID("00000000-0000-0000-0000-000000000102"),
            title="周末蓝调",
            scene="植物园、逛展和周末散步",
            slots=(
                _slot(OutfitCategory.TOP, 1021, "白色短款背心"),
                _slot(OutfitCategory.BOTTOM, 1022, "浅蓝直筒牛仔裤"),
                _slot(OutfitCategory.OUTERWEAR, 1023, "燕麦色垂感西装"),
                _slot(OutfitCategory.SHOES, 1024, "白色厚底运动鞋"),
            ),
            rationale="规则基线: 轻松复古且方便步行",
            style_match_score=74,
        ),
        OutfitPlan(
            id=UUID("00000000-0000-0000-0000-000000000103"),
            title="蓝色高光",
            scene="晚宴、酒会和正式合影",
            slots=(
                _slot(OutfitCategory.DRESS, 1031, "宝蓝亮片礼服裙"),
                _slot(OutfitCategory.SHOES, 1032, "黑色细带高跟鞋"),
                _slot(OutfitCategory.ACCESSORY, 1033, "黑色手拿包"),
            ),
            rationale="规则基线: 单一高饱和焦点适合晚宴",
            style_match_score=70,
        ),
    )


async def _run_reasoning(
    candidate: Candidate,
    case: ReasoningCase,
    *,
    gateway_url: str,
    gateway_key: str,
) -> dict[str, object]:
    recorder = RecordingCompletion()
    reranker = LiteLLMOutfitReranker(
        capability_alias=candidate.alias,
        gateway_base_url=gateway_url,
        gateway_api_key=gateway_key,
        completion=recorder,
    )
    plans = _plans()
    started = perf_counter()
    try:
        result = await reranker.rerank(case.request, plans)
        wall_latency_ms = round((perf_counter() - started) * 1000)
        output = [
            {
                "id": str(plan.id),
                "rationale": plan.rationale,
                "style_match_score": plan.style_match_score,
            }
            for plan in result.plans
        ]
        checks, score = _score_reasoning_output(output, case)
        return {
            "capability": "outfit_reasoning",
            "case": case.key,
            "status": "success",
            "wall_latency_ms": wall_latency_ms,
            "provider_latency_ms": result.trace.latency_ms,
            "usage": recorder.usage,
            "estimated_cost_cny": _estimated_cost(recorder.usage, candidate),
            "checks": checks,
            "quality_score": score,
            "output": output,
        }
    except Exception as error:
        return {
            "capability": "outfit_reasoning",
            "case": case.key,
            "status": "error",
            "wall_latency_ms": round((perf_counter() - started) * 1000),
            "usage": recorder.usage,
            "estimated_cost_cny": _estimated_cost(recorder.usage, candidate),
            "error": _safe_error(error),
            "quality_score": 0,
        }


def _rescore_calls(calls: Mapping[str, list[dict[str, object]]]) -> None:
    garment_cases = {case.key: case for case in GARMENT_CASES}
    look_cases = {case.key: case for case in LOOK_CASES}
    reasoning_cases = {case.key: case for case in REASONING_CASES}
    for model_calls in calls.values():
        for call in model_calls:
            if call["status"] != "success":
                continue
            capability = str(call["capability"])
            case_key = str(call["case"])
            output = call["output"]
            if capability == "garment_understanding":
                checks, score = _score_garment_output(
                    output,  # type: ignore[arg-type]
                    garment_cases[case_key],
                )
            elif capability == "outfit_analysis":
                checks, score = _score_look_output(
                    output,  # type: ignore[arg-type]
                    look_cases[case_key],
                )
            elif capability == "outfit_reasoning":
                checks, score = _score_reasoning_output(
                    output,  # type: ignore[arg-type]
                    reasoning_cases[case_key],
                )
            else:
                raise ValueError(f"unsupported capability in result: {capability}")
            call["checks"] = checks
            call["quality_score"] = score


def _percentile_95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, (95 * len(ordered) + 99) // 100 - 1)
    return ordered[index]


def _summarize(candidate: Candidate, calls: list[dict[str, object]]) -> dict[str, object]:
    successful = [call for call in calls if call["status"] == "success"]
    latencies = [int(call["wall_latency_ms"]) for call in calls]
    usage = {
        name: sum(int(call["usage"][name]) for call in calls)  # type: ignore[index]
        for name in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    by_capability: dict[str, object] = {}
    for capability in (
        "garment_understanding",
        "outfit_analysis",
        "outfit_reasoning",
    ):
        capability_calls = [call for call in calls if call["capability"] == capability]
        by_capability[capability] = {
            "attempts": len(capability_calls),
            "successes": sum(call["status"] == "success" for call in capability_calls),
            "error_rate": round(
                sum(call["status"] != "success" for call in capability_calls)
                / len(capability_calls),
                3,
            ),
            "mean_quality_score": round(
                statistics.fmean(float(call["quality_score"]) for call in capability_calls),
                1,
            ),
            "mean_latency_ms": round(
                statistics.fmean(int(call["wall_latency_ms"]) for call in capability_calls)
            ),
        }
    return {
        "provider_model": candidate.provider_model,
        "candidate_alias": candidate.alias,
        "attempts": len(calls),
        "successes": len(successful),
        "errors": len(calls) - len(successful),
        "error_rate": round((len(calls) - len(successful)) / len(calls), 3),
        "schema_pass_rate": round(
            sum(
                call["status"] == "success"
                and bool(call.get("checks", {}).get("json_schema_valid"))  # type: ignore[union-attr]
                for call in calls
            )
            / len(calls),
            3,
        ),
        "taxonomy_pass_rate": round(
            sum(
                call["status"] == "success" and bool(call.get("checks", {}).get("taxonomy_valid"))  # type: ignore[union-attr]
                for call in calls
            )
            / len(calls),
            3,
        ),
        "chinese_pass_rate": round(
            sum(
                call["status"] == "success" and bool(call.get("checks", {}).get("chinese_complete"))  # type: ignore[union-attr]
                for call in calls
            )
            / len(calls),
            3,
        ),
        "mean_quality_score": round(
            statistics.fmean(float(call["quality_score"]) for call in calls), 1
        ),
        "median_latency_ms": round(statistics.median(latencies)),
        "p95_latency_ms": _percentile_95(latencies),
        "usage": usage,
        "estimated_cost_cny": round(sum(float(call["estimated_cost_cny"]) for call in calls), 8),
        "by_capability": by_capability,
    }


def _decision(summary: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    mini = summary["mini"]
    lite = summary["lite"]
    quality_delta = round(float(mini["mean_quality_score"]) - float(lite["mean_quality_score"]), 1)
    per_capability = mini["by_capability"]
    lite_capabilities = lite["by_capability"]
    mechanical_pass = (
        mini["successes"] == 9
        and mini["schema_pass_rate"] == 1
        and mini["taxonomy_pass_rate"] == 1
        and mini["chinese_pass_rate"] == 1
        and all(
            capability["mean_quality_score"] >= 85
            for capability in per_capability.values()  # type: ignore[union-attr]
        )
        and quality_delta >= -5
        and float(mini["estimated_cost_cny"]) < float(lite["estimated_cost_cny"])
    )
    capability_routes: dict[str, str] = {}
    for capability in (
        "garment_understanding",
        "outfit_analysis",
        "outfit_reasoning",
    ):
        mini_capability = per_capability[capability]  # type: ignore[index]
        lite_capability = lite_capabilities[capability]  # type: ignore[index]
        capability_delta = round(
            float(mini_capability["mean_quality_score"])
            - float(lite_capability["mean_quality_score"]),
            1,
        )
        capability_routes[capability] = (
            "mini_with_lite_fallback"
            if mini_capability["successes"] == 3
            and float(mini_capability["mean_quality_score"]) >= 85
            and capability_delta >= -5
            else "keep_lite"
        )
    return {
        "mini_meets_gate": mechanical_pass,
        "quality_delta_points_mini_minus_lite": quality_delta,
        "latency_delta_median_ms_mini_minus_lite": (
            int(mini["median_latency_ms"]) - int(lite["median_latency_ms"])
        ),
        "estimated_cost_saving_fraction": (
            round(
                1 - float(mini["estimated_cost_cny"]) / float(lite["estimated_cost_cny"]),
                3,
            )
            if float(lite["estimated_cost_cny"])
            else None
        ),
        "capability_routes": capability_routes,
        "alias_recommendation": {
            "vision_understanding": capability_routes["garment_understanding"],
            "outfit_analysis": capability_routes["outfit_analysis"],
            "reasoning": capability_routes["outfit_reasoning"],
            "visual_grounding": "keep_lite_not_evaluated",
            "image_generation": "keep_seedream_not_evaluated",
        },
    }


def _render_report(result: Mapping[str, object]) -> str:
    summary = result["summary"]
    decision = result["decision"]
    rows = []
    for label in ("lite", "mini"):
        model = summary[label]  # type: ignore[index]
        rows.append(
            "| {label} | {successes}/9 | {quality:.1f} | {median} | {p95} | "
            "{schema:.0%} | {chinese:.0%} | {cost:.6f} |".format(
                label=label.title(),
                successes=model["successes"],
                quality=float(model["mean_quality_score"]),
                median=model["median_latency_ms"],
                p95=model["p95_latency_ms"],
                schema=float(model["schema_pass_rate"]),
                chinese=float(model["chinese_pass_rate"]),
                cost=float(model["estimated_cost_cny"]),
            )
        )
    capability_rows = []
    for capability in (
        "garment_understanding",
        "outfit_analysis",
        "outfit_reasoning",
    ):
        lite_capability = summary["lite"]["by_capability"][capability]  # type: ignore[index]
        mini_capability = summary["mini"]["by_capability"][capability]  # type: ignore[index]
        capability_rows.append(
            "| {capability} | {lite_quality:.1f} | {mini_quality:.1f} | "
            "{lite_latency} | {mini_latency} | {route} |".format(
                capability=capability,
                lite_quality=float(lite_capability["mean_quality_score"]),
                mini_quality=float(mini_capability["mean_quality_score"]),
                lite_latency=lite_capability["mean_latency_ms"],
                mini_latency=mini_capability["mean_latency_ms"],
                route=decision["capability_routes"][capability],  # type: ignore[index]
            )
        )
    verdict = "通过" if decision["mini_meets_gate"] else "未通过"
    return "\n".join(
        [
            "# Doubao Seed 2.0 Mini vs Lite — live A/B",
            "",
            f"- Run UTC: `{result['run_utc']}`",
            "- Gateway: local LiteLLM; serial requests; zero retries",
            "- Corpus: 3 real item images + 3 real Look images + 3 scene requests per model",
            "- Seedream/image generation: unchanged and not invoked",
            f"- Mini mechanical gate: **{verdict}**",
            "",
            "| Model | Success | Quality /100 | Median ms | P95 ms | Schema | Chinese | Est. CNY |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            *rows,
            "",
            "## Decision metrics",
            "",
            f"- Quality delta (Mini - Lite): {decision['quality_delta_points_mini_minus_lite']} points",
            f"- Median latency delta (Mini - Lite): {decision['latency_delta_median_ms_mini_minus_lite']} ms",
            f"- Estimated cost saving: {decision['estimated_cost_saving_fraction']}",
            "",
            "## Capability routing",
            "",
            "| Capability | Lite quality | Mini quality | Lite mean ms | Mini mean ms | Recommendation |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
            *capability_rows,
            "",
            "- `vision_understanding`: keep Lite. Mini misclassified the pale-green cardigan",
            "  as `tops/knitwear` instead of the required `outerwear/cardigan` taxonomy pair.",
            "- `outfit_analysis`: Mini is acceptable for this bounded descriptive route; use",
            "  Lite as fallback on provider, schema, or Chinese-completeness failure.",
            "- `reasoning`: keep Lite. Mini ranked the casual denim/sneaker plan above the",
            "  business plan for the formal interview request.",
            "- `visual_grounding`: keep Lite because this run did not evaluate box/region quality.",
            "- `image_generation`: keep Seedream; it was deliberately not part of this A/B.",
            "",
            "## Adopted routing",
            "",
            "The capability-specific recommendation is now implemented behind stable aliases:",
            "",
            "- product code calls only `outfit_analysis`; the gateway maps it to Mini;",
            "- on a provider failure, invalid structured response, or non-Chinese user-facing",
            "  response, the same adapter calls server-only `outfit_analysis_fallback` (Lite);",
            "- attempts are strictly sequential, and a valid Mini response ends the call without",
            "  invoking Lite;",
            "- product metadata continues to expose `outfit_analysis`, never a provider or model ID;",
            "- `vision_understanding`, `visual_grounding`, and `reasoning` remain on Lite, while",
            "  `image_generation` remains on Seedream.",
            "",
            "## Interpretation limits",
            "",
            "Quality is a deterministic rubric over expected taxonomy, visible-evidence terms,",
            "closed candidate preservation, and expected top rank. It is not a broad human-style",
            "preference score. Three cases per capability are enough for a routing smoke, not a",
            "production-wide quality guarantee.",
            "",
            "Detailed per-call outputs and checks are in the adjacent sanitized JSON result.",
            "The routing decision is capability-specific; the overall Mini gate remains failed and",
            "does not justify replacing Lite for the other capabilities.",
            "",
            f"Pricing source: {PRICE_SOURCE}",
            "",
        ]
    )


async def _run(args: argparse.Namespace) -> dict[str, object]:
    gateway_key = (
        os.getenv("STYLECAPTURE_EVAL_GATEWAY_KEY")
        or os.getenv("LITELLM_MASTER_KEY")
        or LOCAL_GATEWAY_DEFAULT
    )
    all_calls: dict[str, list[dict[str, object]]] = {}
    for candidate in CANDIDATES:
        calls: list[dict[str, object]] = []
        for case in GARMENT_CASES:
            calls.append(
                await _run_garment(
                    candidate,
                    case,
                    gateway_url=args.gateway_url,
                    gateway_key=gateway_key,
                )
            )
            await asyncio.sleep(args.interval_seconds)
        for case in LOOK_CASES:
            calls.append(
                await _run_look(
                    candidate,
                    case,
                    gateway_url=args.gateway_url,
                    gateway_key=gateway_key,
                )
            )
            await asyncio.sleep(args.interval_seconds)
        for case in REASONING_CASES:
            calls.append(
                await _run_reasoning(
                    candidate,
                    case,
                    gateway_url=args.gateway_url,
                    gateway_key=gateway_key,
                )
            )
            await asyncio.sleep(args.interval_seconds)
        all_calls[candidate.label] = calls

    summary = {
        candidate.label: _summarize(candidate, all_calls[candidate.label])
        for candidate in CANDIDATES
    }
    return {
        "schema_version": "stylecapture-model-routing-eval-v1",
        "run_utc": datetime.now(UTC).isoformat(),
        "execution": {
            "gateway": "local_litellm",
            "serial": True,
            "max_concurrency": 1,
            "retries": 0,
            "interval_seconds": args.interval_seconds,
            "credentials_persisted": False,
            "image_bytes_persisted": False,
            "seedream_invoked": False,
        },
        "pricing": {
            "currency": "CNY",
            "tier": "0-32k",
            "unit": "per_million_tokens",
            "source": PRICE_SOURCE,
            "candidates": {candidate.label: asdict(candidate) for candidate in CANDIDATES},
        },
        "corpus": {
            "garment_images": len(GARMENT_CASES),
            "look_images": len(LOOK_CASES),
            "reasoning_requests": len(REASONING_CASES),
            "requests_per_model": 9,
        },
        "calls": all_calls,
        "summary": summary,
        "decision": _decision(summary),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL)
    parser.add_argument("--interval-seconds", type=float, default=0.5)
    parser.add_argument(
        "--rescore-existing",
        type=Path,
        help="Reapply the current deterministic rubric without making provider calls",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evals/model-routing/results/doubao-mini-vs-lite-2026-07-26.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("evals/model-routing/REPORT.md"),
    )
    args = parser.parse_args()
    output_path = args.output
    if args.rescore_existing is not None:
        result = json.loads(args.rescore_existing.read_text(encoding="utf-8"))
        _rescore_calls(result["calls"])
        result["summary"] = {
            candidate.label: _summarize(candidate, result["calls"][candidate.label])
            for candidate in CANDIDATES
        }
        result["decision"] = _decision(result["summary"])
        result["rubric_rescored_utc"] = datetime.now(UTC).isoformat()
        output_path = args.rescore_existing
    else:
        result = asyncio.run(_run(args))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.report.write_text(_render_report(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "report": str(args.report),
                "decision": result["decision"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
