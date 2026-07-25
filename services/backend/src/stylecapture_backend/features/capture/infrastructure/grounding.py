from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any, cast

from litellm import acompletion

from stylecapture_backend.features.capture.domain import FeedSelection, ImagePayload
from stylecapture_backend.features.capture.grounding import (
    GroundingAnalysis,
    GroundingCandidate,
    NormalizedBox,
)
from stylecapture_backend.features.capture.infrastructure.image_data import (
    image_to_jpeg_data_url,
)
from stylecapture_backend.features.capture.processing import ModelMetadata, ProviderError
from stylecapture_backend.features.wardrobe.taxonomy import (
    TAXONOMY_VERSION,
    GarmentCategory,
)

GROUNDING_PROMPT_VERSION = "outfit-grounding-v1"
GROUNDING_SCHEMA_VERSION = "ark-bbox-tags-v1"

_GROUNDING_LINE = re.compile(
    r"^component=(?P<label>[a-z0-9_]+);\s*"
    r"category=(?P<category>[a-z_]+);\s*"
    r"confidence=(?P<confidence>(?:0(?:\.\d+)?|1(?:\.0+)?));\s*"
    r"visible=(?P<visible>(?:0(?:\.\d+)?|1(?:\.0+)?));\s*"
    r"<bbox>\s*(?P<x_min>\d{1,4})\s+(?P<y_min>\d{1,4})\s+"
    r"(?P<x_max>\d{1,4})\s+(?P<y_max>\d{1,4})\s*</bbox>$"
)

CompletionCall = Callable[..., Awaitable[object]]


class LiteLLMVisualGrounder:
    """Thin hosted grounding adapter; it never claims to return a pixel mask."""

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
            raise ValueError("grounding capability alias must not be empty")
        self._alias = capability_alias
        self._base_url = gateway_base_url.rstrip("/")
        self._api_key = gateway_api_key
        self._completion = completion
        self._timeout_seconds = timeout_seconds

    async def ground(
        self,
        image: ImagePayload,
        *,
        scope: FeedSelection,
    ) -> GroundingAnalysis:
        data_url = _grounding_data_url(image)
        started = perf_counter()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await self._completion(
                    model=f"openai/{self._alias}",
                    api_base=self._base_url,
                    api_key=self._api_key,
                    messages=_messages(data_url, scope=scope),
                    temperature=0,
                    max_tokens=1200,
                    num_retries=0,
                )
        except Exception as error:
            raise ProviderError(
                "grounding_unavailable",
                "Visual grounding is temporarily unavailable",
                retryable=True,
            ) from error

        latency_ms = max(0, round((perf_counter() - started) * 1000))
        try:
            raw = cast(Any, response)
            content = raw.choices[0].message.content
            if not isinstance(content, str):
                raise TypeError("grounding response content is not text")
            candidates = parse_grounding_text(content)
            provider_model = str(raw.model)
        except (AttributeError, IndexError, TypeError, ValueError) as error:
            raise ProviderError(
                "grounding_schema_invalid",
                "Visual grounding returned invalid component coordinates",
                retryable=True,
            ) from error

        return GroundingAnalysis(
            candidates=candidates,
            metadata=ModelMetadata(
                capability_alias=self._alias,
                provider_model=provider_model,
                prompt_version=GROUNDING_PROMPT_VERSION,
                schema_version=GROUNDING_SCHEMA_VERSION,
                taxonomy_version=TAXONOMY_VERSION,
                latency_ms=latency_ms,
            ),
        )


def parse_grounding_text(content: str) -> tuple[GroundingCandidate, ...]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        raise ValueError("grounding response is empty")

    candidates: list[GroundingCandidate] = []
    for line in lines:
        match = _GROUNDING_LINE.fullmatch(line)
        if match is None:
            raise ValueError("grounding response line does not match the tag contract")
        candidates.append(
            GroundingCandidate(
                label=match.group("label"),
                category=GarmentCategory(match.group("category")),
                confidence=float(match.group("confidence")),
                visible_fraction=float(match.group("visible")),
                box=NormalizedBox(
                    int(match.group("x_min")),
                    int(match.group("y_min")),
                    int(match.group("x_max")),
                    int(match.group("y_max")),
                ),
            )
        )

    labels = [candidate.label for candidate in candidates]
    if len(labels) != len(set(labels)):
        raise ValueError("grounding candidate labels must be unique")
    return tuple(candidates)


def _messages(
    data_url: str,
    *,
    scope: FeedSelection,
) -> list[dict[str, object]]:
    points = ", ".join(f"({point.x:.6f},{point.y:.6f})" for point in scope.polygon)
    categories = ", ".join(category.value for category in GarmentCategory)
    return [
        {
            "role": "system",
            "content": (
                "You locate visible garment and accessory components inside a user-selected "
                "outfit. Use only visible evidence. Do not invent occluded items, brands, "
                "materials, or pixel masks. Return no JSON and no Markdown. Return exactly one "
                "line per visible component using this contract:\n"
                "component=<lowercase_stable_id>; category=<category>; confidence=<0..1>; "
                "visible=<0..1>; <bbox>x1 y1 x2 y2</bbox>\n"
                "Bounding-box coordinates use the Ark visual-grounding 0..999 coordinate space. "
                "Pairs such as shoes are one wardrobe component. Component IDs must be unique. "
                f"Allowed categories: {categories}."
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Locate outfit components only inside selection_key={scope.selection_key!r}. "
                        f"The normalized closed user polygon is [{points}]. "
                        "Return coordinates only in the required "
                        "<bbox>x1 y1 x2 y2</bbox> tag contract."
                    ),
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]


def _grounding_data_url(image: ImagePayload) -> str:
    try:
        return image_to_jpeg_data_url(image)
    except (OSError, ValueError) as error:
        raise ProviderError(
            "grounding_image_invalid",
            "The source image could not be prepared for visual grounding",
            retryable=False,
        ) from error
