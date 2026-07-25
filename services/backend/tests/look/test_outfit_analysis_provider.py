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
  "color": {"value": "米白与藏青", "confidence": 0.91},
  "silhouette": {"value": "宽松直筒", "confidence": 0.87},
  "material": {"value": "亚麻与棉", "confidence": 0.82},
  "layering": {"value": "衬衫叠搭长裤", "confidence": 0.84},
  "focal_point": {"value": "敞开领口", "confidence": 0.79},
  "scene": {"value": "城市街道", "confidence": 0.76},
  "style": {"value": "极简休闲", "confidence": 0.92}
}
"""

ENGLISH_ANALYSIS = """
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


class SequencedCompletion:
    def __init__(self, *results: str | Exception) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(
            model="provider-outfit-v1",
            choices=[SimpleNamespace(message=SimpleNamespace(content=result))],
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
        capability_alias="outfit_analysis",
        latency_ms=13,
    )

    assert analysis.color.value == "米白与藏青"
    assert analysis.style.confidence == 0.92
    assert analysis.metadata.capability_alias == "outfit_analysis"
    assert analysis.metadata.model_version == "outfit-analysis-model-v1"
    assert analysis.metadata.prompt_version == LOOK_ANALYSIS_PROMPT_VERSION
    assert analysis.metadata.schema_version == LOOK_ANALYSIS_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_litellm_outfit_analyzer_requests_chinese_user_facing_values() -> None:
    completion = RecordingCompletion(VALID_ANALYSIS)
    analyzer = LiteLLMOutfitAnalyzer(
        capability_alias="outfit_analysis",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=completion,
    )

    await analyzer.analyze(image(), components=())

    system_prompt = completion.calls[0]["messages"][0]["content"]
    assert "Simplified Chinese" in system_prompt
    assert "keep only the required JSON keys in English" in system_prompt


@pytest.mark.parametrize(
    "content",
    [
        "{}",
        VALID_ANALYSIS.replace('"style"', '"styles"', 1),
        VALID_ANALYSIS.replace('"confidence": 0.92', '"confidence": 1.2'),
        VALID_ANALYSIS.replace('"极简休闲"', '""'),
        VALID_ANALYSIS.replace("\n}", ', "provider_secret": "sk-sensitive-value"\\n}'),
    ],
)
def test_parse_look_analysis_rejects_malformed_extra_or_invalid_content(content: str) -> None:
    with pytest.raises(ValueError):
        parse_look_analysis(
            content,
            capability_alias="outfit_analysis",
            latency_ms=13,
        )


def test_parse_look_analysis_rejects_non_chinese_user_facing_values() -> None:
    # Catches: accepting a structurally valid response that violates the Chinese UI contract.
    with pytest.raises(ValueError, match="Chinese"):
        parse_look_analysis(
            ENGLISH_ANALYSIS,
            capability_alias="outfit_analysis",
            latency_ms=13,
        )


@pytest.mark.asyncio
async def test_litellm_outfit_analyzer_uses_alias_and_stores_provenance() -> None:
    completion = RecordingCompletion(VALID_ANALYSIS)
    analyzer = LiteLLMOutfitAnalyzer(
        capability_alias="outfit_analysis",
        fallback_alias="outfit_analysis_fallback",
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
    assert analysis.metadata.model_version == "outfit-analysis-model-v1"
    assert analysis.metadata.capability_alias == "outfit_analysis"
    assert len(completion.calls) == 1


@pytest.mark.parametrize(
    "primary_result",
    [
        ConnectionError("primary unavailable"),
        "{}",
        ENGLISH_ANALYSIS,
    ],
    ids=("provider-failure", "schema-failure", "chinese-contract-failure"),
)
@pytest.mark.asyncio
async def test_litellm_outfit_analyzer_falls_back_sequentially(
    primary_result: str | Exception,
) -> None:
    # Catches: a failed Mini attempt escaping instead of invoking the Lite fallback once.
    completion = SequencedCompletion(primary_result, VALID_ANALYSIS)
    analyzer = LiteLLMOutfitAnalyzer(
        capability_alias="outfit_analysis",
        fallback_alias="outfit_analysis_fallback",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=completion,
    )

    analysis = await analyzer.analyze(image(), components=())

    assert [call["model"] for call in completion.calls] == [
        "openai/outfit_analysis",
        "openai/outfit_analysis_fallback",
    ]
    assert analysis.metadata.capability_alias == "outfit_analysis"
    assert analysis.color.value == "米白与藏青"


@pytest.mark.asyncio
async def test_litellm_outfit_analyzer_sanitizes_exhausted_fallback() -> None:
    # Catches: leaking either provider failure after both sequential attempts fail.
    completion = SequencedCompletion(
        ConnectionError("primary leaked sk-sensitive-primary"),
        ConnectionError("fallback leaked sk-sensitive-fallback"),
    )
    analyzer = LiteLLMOutfitAnalyzer(
        capability_alias="outfit_analysis",
        fallback_alias="outfit_analysis_fallback",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=completion,
    )

    with pytest.raises(ProviderError) as error:
        await analyzer.analyze(image(), components=())

    assert [call["model"] for call in completion.calls] == [
        "openai/outfit_analysis",
        "openai/outfit_analysis_fallback",
    ]
    assert error.value.code == "outfit_analysis_unavailable"
    assert "sensitive" not in error.value.message


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
