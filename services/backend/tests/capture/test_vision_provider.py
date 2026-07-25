import json
from types import SimpleNamespace
from typing import Any

import pytest
from stylecapture_backend.features.capture.domain import (
    FeedSelection,
    NormalizedPoint,
)
from stylecapture_backend.features.capture.infrastructure.providers import (
    GARMENT_PROMPT_VERSION,
    GARMENT_SCHEMA_VERSION,
    LiteLLMVisionTagger,
)
from stylecapture_backend.features.capture.processing import ImagePayload, ProviderError


def valid_response() -> dict[str, object]:
    return {
        "category": {"value": "tops", "confidence": 0.98},
        "subcategory": {"value": "shirt", "confidence": 0.95},
        "description": {"value": "一件蓝色宽松衬衫", "confidence": 0.91},
        "colors": {"value": ["blue"], "confidence": 0.96},
        "materials": {"value": ["cotton"], "confidence": 0.74},
        "pattern": {"value": "solid", "confidence": 0.9},
        "silhouette": {"value": "straight", "confidence": 0.83},
        "fit": {"value": "relaxed", "confidence": 0.82},
        "styles": {"value": ["casual", "minimal"], "confidence": 0.88},
        "seasons": {"value": ["spring", "autumn"], "confidence": 0.79},
        "occasions": {"value": ["daily", "work"], "confidence": 0.77},
        "length": {"value": "regular", "confidence": 0.84},
        "neckline": {"value": "collared", "confidence": 0.96},
        "sleeve_type": {"value": "long_sleeve", "confidence": 0.97},
        "details": {"value": ["button_front"], "confidence": 0.86},
    }


class RecordingCompletion:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            model="provider-model-v1",
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(self.payload, ensure_ascii=False))
                )
            ],
        )


def image() -> ImagePayload:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (32, 48), color=(65, 105, 225)).save(buffer, format="PNG")
    return ImagePayload(
        object_key="originals/garment.png",
        content_type="image/png",
        body=buffer.getvalue(),
        sha256="a" * 64,
    )


@pytest.mark.asyncio
async def test_litellm_adapter_uses_capability_alias_and_strict_schema() -> None:
    completion = RecordingCompletion(valid_response())
    tagger = LiteLLMVisionTagger(
        capability_alias="vision_understanding",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=completion,
    )

    result = await tagger.describe(image())

    assert result.fields["category"].value == "tops"
    assert result.fields["colors"].value == ["blue"]
    assert {field.model_version for field in result.fields.values()} == {"vision_understanding"}
    assert result.metadata.capability_alias == "vision_understanding"
    assert result.metadata.provider_model == "provider-model-v1"
    assert result.metadata.prompt_version == GARMENT_PROMPT_VERSION
    assert result.metadata.schema_version == GARMENT_SCHEMA_VERSION
    call = completion.calls[0]
    assert call["model"] == "openai/vision_understanding"
    assert call["api_base"] == "http://litellm:4000/v1"
    assert call["api_key"] == "internal-gateway-key"
    assert call["num_retries"] == 0
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["strict"] is True
    image_url = call["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")
    assert "provider-model-v1" not in json.dumps(call)
    assert "provider-model-v1" not in json.dumps(
        {
            name: {
                "value": field.value,
                "confidence": field.confidence,
                "model_version": field.model_version,
            }
            for name, field in result.fields.items()
        }
    )


@pytest.mark.asyncio
async def test_litellm_feed_prompt_preserves_selection_identity_and_boundary() -> None:
    completion = RecordingCompletion(valid_response())
    tagger = LiteLLMVisionTagger(
        capability_alias="vision_understanding",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=completion,
    )
    selection = FeedSelection(
        selection_key="jacket",
        polygon=(
            NormalizedPoint(0.1, 0.2),
            NormalizedPoint(0.7, 0.2),
            NormalizedPoint(0.7, 0.8),
            NormalizedPoint(0.1, 0.8),
        ),
    )

    await tagger.describe(image(), selection=selection)

    prompt = completion.calls[0]["messages"][1]["content"][0]["text"]
    assert "selection_key='jacket'" in prompt
    assert "(0.100000,0.200000)" in prompt
    assert "(0.700000,0.800000)" in prompt
    assert "isolated pixel region" in prompt


@pytest.mark.asyncio
async def test_litellm_adapter_rejects_invalid_taxonomy_without_fixed_fallback() -> None:
    payload = valid_response()
    payload["category"] = {"value": "mystery-fashion", "confidence": 0.99}
    completion = RecordingCompletion(payload)
    tagger = LiteLLMVisionTagger(
        capability_alias="vision_understanding",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=completion,
    )

    with pytest.raises(ProviderError) as error:
        await tagger.describe(image())

    assert error.value.code == "vision_schema_invalid"
    assert error.value.retryable is True


@pytest.mark.asyncio
async def test_litellm_adapter_sanitizes_gateway_failures() -> None:
    async def failing_completion(**kwargs: Any) -> object:
        raise ConnectionError("secret provider endpoint rejected sk-sensitive-value")

    tagger = LiteLLMVisionTagger(
        capability_alias="vision_understanding",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=failing_completion,
    )

    with pytest.raises(ProviderError) as error:
        await tagger.describe(image())

    assert error.value.code == "vision_unavailable"
    assert "secret" not in error.value.message
    assert error.value.retryable is True
