from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any, cast

from litellm import acompletion
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from stylecapture_backend.features.capture.domain import FeedSelection
from stylecapture_backend.features.capture.infrastructure.image_data import (
    image_to_jpeg_data_url,
)
from stylecapture_backend.features.capture.processing import (
    ImagePayload,
    ModelMetadata,
    ProviderError,
    VisionAnalysis,
)
from stylecapture_backend.features.wardrobe.domain import ModelField
from stylecapture_backend.features.wardrobe.taxonomy import (
    TAXONOMY_VERSION,
    GarmentCategory,
    is_valid_subcategory,
    taxonomy_prompt,
)

GARMENT_PROMPT_VERSION = "garment-v1"
GARMENT_SCHEMA_VERSION = "garment-v1"


class ConfidentText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)


class ConfidentValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: list[str] = Field(max_length=12)
    confidence: float = Field(ge=0, le=1)


class ConfidentCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: GarmentCategory
    confidence: float = Field(ge=0, le=1)


class GarmentVisionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ConfidentCategory
    subcategory: ConfidentText
    description: ConfidentText
    colors: ConfidentValues
    materials: ConfidentValues
    pattern: ConfidentText
    silhouette: ConfidentText
    fit: ConfidentText
    styles: ConfidentValues
    seasons: ConfidentValues
    occasions: ConfidentValues
    length: ConfidentText
    neckline: ConfidentText
    sleeve_type: ConfidentText
    details: ConfidentValues

    @model_validator(mode="after")
    def validate_taxonomy_pair(self) -> GarmentVisionSchema:
        if not is_valid_subcategory(self.category.value, self.subcategory.value):
            raise ValueError(
                f"{self.subcategory.value} is not valid for {self.category.value.value}"
            )
        return self


CompletionCall = Callable[..., Awaitable[object]]


class LiteLLMVisionTagger:
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
            raise ValueError("vision capability alias must not be empty")
        self._alias = capability_alias
        self._base_url = gateway_base_url.rstrip("/")
        self._api_key = gateway_api_key
        self._completion = completion
        self._timeout_seconds = timeout_seconds

    async def describe(
        self,
        image: ImagePayload,
        *,
        selection: FeedSelection | None = None,
    ) -> VisionAnalysis:
        data_url = _vision_data_url(image)
        started = perf_counter()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await self._completion(
                    model=f"openai/{self._alias}",
                    api_base=self._base_url,
                    api_key=self._api_key,
                    messages=_messages(data_url, selection=selection),
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "garment_analysis",
                            "strict": True,
                            "schema": GarmentVisionSchema.model_json_schema(),
                        },
                    },
                    temperature=0,
                    max_tokens=1400,
                    num_retries=0,
                )
        except Exception as error:
            raise ProviderError(
                "vision_unavailable",
                "Vision understanding is temporarily unavailable",
                retryable=True,
            ) from error

        latency_ms = max(0, round((perf_counter() - started) * 1000))
        try:
            raw = cast(Any, response)
            content = raw.choices[0].message.content
            if not isinstance(content, str):
                raise TypeError("vision response content is not text")
            parsed = GarmentVisionSchema.model_validate_json(content)
            provider_model = str(raw.model)
        except (
            AttributeError,
            IndexError,
            TypeError,
            ValueError,
            ValidationError,
            json.JSONDecodeError,
        ) as error:
            raise ProviderError(
                "vision_schema_invalid",
                "Vision understanding returned an invalid garment schema",
                retryable=True,
            ) from error

        return VisionAnalysis(
            fields=_model_fields(parsed, self._alias),
            metadata=ModelMetadata(
                capability_alias=self._alias,
                provider_model=provider_model,
                prompt_version=GARMENT_PROMPT_VERSION,
                schema_version=GARMENT_SCHEMA_VERSION,
                taxonomy_version=TAXONOMY_VERSION,
                latency_ms=latency_ms,
            ),
        )


def _messages(
    data_url: str,
    *,
    selection: FeedSelection | None = None,
) -> list[dict[str, object]]:
    selection_instruction = ""
    if selection is not None:
        points = ", ".join(f"({point.x:.6f},{point.y:.6f})" for point in selection.polygon)
        selection_instruction = (
            f" Analyze only selection_key={selection.selection_key!r}. "
            f"Its normalized closed polygon is [{points}]. "
            "The supplied image is the corresponding isolated pixel region."
        )
    return [
        {
            "role": "system",
            "content": (
                "You are a garment asset analyst. Return only the requested strict JSON schema. "
                "Describe visible evidence conservatively, use lowercase stable IDs, and never "
                "invent a brand, material, or detail that is not visible.\n\n"
                f"{taxonomy_prompt()}"
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Analyze the primary garment or accessory in this image for a digital "
                        "wardrobe. Confidence is field-specific from 0 to 1."
                        f"{selection_instruction}"
                    ),
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]


def _vision_data_url(image: ImagePayload) -> str:
    try:
        return image_to_jpeg_data_url(image)
    except (OSError, ValueError) as error:
        raise ProviderError(
            "vision_image_invalid",
            "The uploaded image could not be prepared for vision understanding",
            retryable=False,
        ) from error


def _model_fields(
    parsed: GarmentVisionSchema,
    model_version_alias: str,
) -> dict[str, ModelField]:
    values: dict[str, ConfidentText | ConfidentValues | ConfidentCategory] = {
        "category": parsed.category,
        "subcategory": parsed.subcategory,
        "description": parsed.description,
        "colors": parsed.colors,
        "materials": parsed.materials,
        "pattern": parsed.pattern,
        "silhouette": parsed.silhouette,
        "fit": parsed.fit,
        "styles": parsed.styles,
        "seasons": parsed.seasons,
        "occasions": parsed.occasions,
        "length": parsed.length,
        "neckline": parsed.neckline,
        "sleeve_type": parsed.sleeve_type,
        "details": parsed.details,
    }
    fields: dict[str, ModelField] = {}
    for name, field in values.items():
        value: object = field.value
        if isinstance(value, GarmentCategory):
            value = value.value
        fields[name] = ModelField(
            value=value,
            confidence=field.confidence,
            model_version=model_version_alias,
        )
    return fields
