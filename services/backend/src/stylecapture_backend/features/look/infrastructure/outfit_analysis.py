from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from time import perf_counter
from typing import Any, cast

from litellm import acompletion

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.capture.infrastructure.image_data import (
    image_to_jpeg_data_url,
)
from stylecapture_backend.features.capture.processing import ProviderError
from stylecapture_backend.features.look.domain import (
    LookAnalysis,
    LookAnalysisField,
    LookAnalysisMetadata,
    LookComponent,
)
from stylecapture_backend.features.wardrobe.taxonomy import TAXONOMY_VERSION

LOOK_ANALYSIS_PROMPT_VERSION = "outfit-analysis-zh-v2"
LOOK_ANALYSIS_MODEL_VERSION = "outfit-analysis-model-v1"
LOOK_ANALYSIS_SCHEMA_VERSION = "look-analysis-v1"

_FIELD_NAMES = frozenset(
    {
        "color",
        "silhouette",
        "material",
        "layering",
        "focal_point",
        "scene",
        "style",
    }
)

CompletionCall = Callable[..., Awaitable[object]]


class LiteLLMOutfitAnalyzer:
    def __init__(
        self,
        *,
        capability_alias: str,
        gateway_base_url: str,
        gateway_api_key: str,
        completion: CompletionCall = acompletion,
        timeout_seconds: float = 45,
    ) -> None:
        if not capability_alias.strip():
            raise ValueError("outfit analysis capability alias must not be empty")
        self._alias = capability_alias
        self._base_url = gateway_base_url.rstrip("/")
        self._api_key = gateway_api_key
        self._completion = completion
        self._timeout_seconds = timeout_seconds

    async def analyze(
        self,
        image: ImagePayload,
        *,
        components: tuple[LookComponent, ...],
    ) -> LookAnalysis:
        data_url = _analysis_data_url(image)
        started = perf_counter()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await self._completion(
                    model=f"openai/{self._alias}",
                    api_base=self._base_url,
                    api_key=self._api_key,
                    messages=_messages(data_url, components=components),
                    temperature=0,
                    max_tokens=900,
                    num_retries=0,
                )
        except Exception as error:
            raise ProviderError(
                "outfit_analysis_unavailable",
                "Outfit analysis is temporarily unavailable",
                retryable=True,
            ) from error

        latency_ms = max(0, round((perf_counter() - started) * 1000))
        try:
            raw = cast(Any, response)
            content = raw.choices[0].message.content
            if not isinstance(content, str):
                raise TypeError("outfit analysis response content is not text")
            return parse_look_analysis(
                content,
                capability_alias=self._alias,
                latency_ms=latency_ms,
            )
        except (AttributeError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ProviderError(
                "outfit_analysis_schema_invalid",
                "Outfit analysis returned invalid structured content",
                retryable=True,
            ) from error


def parse_look_analysis(
    content: str,
    *,
    capability_alias: str,
    latency_ms: int,
) -> LookAnalysis:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("look analysis must be an object")
    if set(payload) != _FIELD_NAMES:
        raise ValueError("look analysis contains unsupported fields")

    fields = {
        name: _field_from_payload(cast(Mapping[str, object], payload[name]))
        for name in _FIELD_NAMES
    }
    metadata = LookAnalysisMetadata(
        capability_alias=capability_alias,
        model_version=LOOK_ANALYSIS_MODEL_VERSION,
        prompt_version=LOOK_ANALYSIS_PROMPT_VERSION,
        schema_version=LOOK_ANALYSIS_SCHEMA_VERSION,
        taxonomy_version=TAXONOMY_VERSION,
        latency_ms=latency_ms,
    )
    return LookAnalysis(
        color=fields["color"],
        silhouette=fields["silhouette"],
        material=fields["material"],
        layering=fields["layering"],
        focal_point=fields["focal_point"],
        scene=fields["scene"],
        style=fields["style"],
        metadata=metadata,
    )


def _field_from_payload(payload: Mapping[str, object]) -> LookAnalysisField:
    if set(payload) != {"value", "confidence"}:
        raise ValueError("look analysis field contains unsupported keys")
    value = payload["value"]
    confidence = payload["confidence"]
    if not isinstance(value, str):
        raise ValueError("look analysis field value must be text")
    if not isinstance(confidence, int | float):
        raise ValueError("look analysis field confidence must be numeric")
    return LookAnalysisField(value=value, confidence=float(confidence))


def _messages(
    data_url: str,
    *,
    components: tuple[LookComponent, ...],
) -> list[dict[str, object]]:
    component_lines = "\n".join(
        (
            f"- {component.component_key}: role={component.role or 'unknown'}, "
            f"confidence={component.confidence:.2f}"
        )
        for component in components
    )
    return [
        {
            "role": "system",
            "content": (
                "Analyze the outfit relationships visible in the image. Use only visible "
                "evidence and the listed reliable components. Return strict JSON only, with "
                "exactly these top-level keys: color, silhouette, material, layering, "
                "focal_point, scene, style. Each value must be an object with string value "
                "written in concise, natural Simplified Chinese and numeric confidence "
                "between 0 and 1. All user-facing values must be Chinese; keep only the "
                "required JSON keys in English. Do not include provider names, "
                "secrets, hidden chain of thought, markdown, or extra keys."
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Reliable components:\n{component_lines if component_lines else '- none'}"
                    ),
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]


def _analysis_data_url(image: ImagePayload) -> str:
    try:
        return image_to_jpeg_data_url(image)
    except (OSError, ValueError) as error:
        raise ProviderError(
            "outfit_analysis_image_invalid",
            "The source image could not be prepared for outfit analysis",
            retryable=False,
        ) from error
