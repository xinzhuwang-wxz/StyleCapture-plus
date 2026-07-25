from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.capture.processing import ProviderError
from stylecapture_backend.features.look.infrastructure.outfit_analysis import (
    LOOK_ANALYSIS_PROMPT_VERSION,
    LOOK_ANALYSIS_SCHEMA_VERSION,
    LiteLLMOutfitAnalyzer,
    parse_look_analysis,
)

VALID_ANALYSIS = """
{
  "color": {"value": "cream and navy", "confidence": 0.91},
  "silhouette": {"value": "relaxed", "confidence": 0.87},
  "material": {"value": "linen and cotton", "confidence": 0.82},
  "layering": {"value": "shirt over trousers", "confidence": 0.84},
  "focal_point": {"value": "open collar", "confidence": 0.79},
  "scene": {"value": "street style", "confidence": 0.76},
  "style": {"value": "minimal casual", "confidence": 0.92}
}
"""


class RecordingCompletion:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            model="provider-outfit-v1",
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))],
        )


def image() -> ImagePayload:
    buffer = BytesIO()
    Image.new("RGB", (40, 60), color=(220, 210, 190)).save(buffer, format="PNG")
    return ImagePayload(
        object_key="originals/feed/frame.png",
        content_type="image/png",
        body=buffer.getvalue(),
        sha256="a" * 64,
    )


def test_parse_look_analysis_accepts_strict_expected_schema() -> None:
    analysis = parse_look_analysis(
        VALID_ANALYSIS,
        provider_model="provider-outfit-v1",
        capability_alias="outfit_analysis",
        latency_ms=13,
    )

    assert analysis.color.value == "cream and navy"
    assert analysis.style.confidence == 0.92
    assert analysis.metadata.capability_alias == "outfit_analysis"
    assert analysis.metadata.provider_model == "provider-outfit-v1"
    assert analysis.metadata.prompt_version == LOOK_ANALYSIS_PROMPT_VERSION
    assert analysis.metadata.schema_version == LOOK_ANALYSIS_SCHEMA_VERSION


@pytest.mark.parametrize(
    "content",
    [
        "{}",
        VALID_ANALYSIS.replace('"style"', '"styles"', 1),
        VALID_ANALYSIS.replace('"confidence": 0.92', '"confidence": 1.2'),
        VALID_ANALYSIS.replace('"minimal casual"', '""'),
        VALID_ANALYSIS.replace("\n}", ', "provider_secret": "sk-sensitive-value"\\n}'),
    ],
)
def test_parse_look_analysis_rejects_malformed_extra_or_invalid_content(content: str) -> None:
    with pytest.raises(ValueError):
        parse_look_analysis(
            content,
            provider_model="provider-outfit-v1",
            capability_alias="outfit_analysis",
            latency_ms=13,
        )


@pytest.mark.asyncio
async def test_litellm_outfit_analyzer_uses_alias_and_stores_provenance() -> None:
    completion = RecordingCompletion(VALID_ANALYSIS)
    analyzer = LiteLLMOutfitAnalyzer(
        capability_alias="outfit_analysis",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=completion,
    )

    analysis = await analyzer.analyze(image(), components=())

    call = completion.calls[0]
    assert call["model"] == "openai/outfit_analysis"
    assert call["api_base"] == "http://litellm:4000/v1"
    assert call["api_key"] == "internal-gateway-key"
    assert call["temperature"] == 0
    assert call["num_retries"] == 0
    assert analysis.metadata.provider_model == "provider-outfit-v1"
    assert analysis.metadata.capability_alias == "outfit_analysis"


@pytest.mark.asyncio
async def test_litellm_outfit_analyzer_sanitizes_provider_failures() -> None:
    async def failing_completion(**kwargs: Any) -> object:
        raise ConnectionError("provider leaked sk-sensitive-value")

    analyzer = LiteLLMOutfitAnalyzer(
        capability_alias="outfit_analysis",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=failing_completion,
    )

    with pytest.raises(ProviderError) as error:
        await analyzer.analyze(image(), components=())

    assert error.value.code == "outfit_analysis_unavailable"
    assert "secret" not in error.value.message
    assert error.value.retryable is True
