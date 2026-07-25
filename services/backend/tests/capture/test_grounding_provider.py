from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image
from stylecapture_backend.features.capture.domain import (
    FeedSelection,
    ImagePayload,
    NormalizedPoint,
)
from stylecapture_backend.features.capture.grounding import NormalizedBox
from stylecapture_backend.features.capture.infrastructure.grounding import (
    GROUNDING_PROMPT_VERSION,
    GROUNDING_SCHEMA_VERSION,
    LiteLLMVisualGrounder,
    parse_grounding_text,
)
from stylecapture_backend.features.capture.processing import ProviderError
from stylecapture_backend.features.wardrobe.taxonomy import GarmentCategory


class RecordingCompletion:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(
            model="doubao-grounding-provider-v1",
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))],
        )


def image() -> ImagePayload:
    buffer = BytesIO()
    Image.new("RGB", (40, 60), color=(220, 210, 190)).save(buffer, format="PNG")
    return ImagePayload(
        object_key="originals/look.png",
        content_type="image/png",
        body=buffer.getvalue(),
        sha256="b" * 64,
    )


def selection() -> FeedSelection:
    return FeedSelection(
        selection_key="whole-look",
        polygon=(
            NormalizedPoint(0.1, 0.1),
            NormalizedPoint(0.9, 0.1),
            NormalizedPoint(0.9, 0.9),
            NormalizedPoint(0.1, 0.9),
        ),
    )


def valid_grounding_text() -> str:
    return "\n".join(
        (
            "component=linen_shirt; category=tops; confidence=0.96; "
            "visible=0.92; <bbox>120 110 720 510</bbox>",
            "component=wide_trousers; category=bottoms; confidence=0.91; "
            "visible=0.88; <bbox>180 480 760 940</bbox>",
        )
    )


def test_parser_preserves_provider_coordinates_and_canonical_categories() -> None:
    candidates = parse_grounding_text(valid_grounding_text())

    assert len(candidates) == 2
    assert candidates[0].label == "linen_shirt"
    assert candidates[0].category is GarmentCategory.TOPS
    assert candidates[0].box == NormalizedBox(120, 110, 720, 510)
    assert candidates[1].visible_fraction == 0.88


@pytest.mark.parametrize(
    "content",
    [
        "",
        "component=shirt; category=tops; confidence=0.9; visible=0.8;",
        (
            "component=shirt; category=tops; confidence=0.9; "
            "visible=0.8; <bbox>720 110 120 510</bbox>"
        ),
        (
            "component=shirt; category=unknown; confidence=0.9; "
            "visible=0.8; <bbox>120 110 720 510</bbox>"
        ),
        (
            "component=shirt; category=tops; confidence=1.4; "
            "visible=0.8; <bbox>120 110 720 510</bbox>"
        ),
        (
            "component=shirt; category=tops; confidence=0.9; "
            "visible=0.8; <bbox>120 110 1020 510</bbox>"
        ),
    ],
)
def test_parser_rejects_incomplete_or_invalid_grounding(content: str) -> None:
    with pytest.raises(ValueError):
        parse_grounding_text(content)


@pytest.mark.asyncio
async def test_litellm_grounder_uses_alias_and_ark_tag_contract() -> None:
    completion = RecordingCompletion(valid_grounding_text())
    grounder = LiteLLMVisualGrounder(
        capability_alias="visual_grounding",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=completion,
    )

    result = await grounder.ground(image(), scope=selection())

    assert len(result.candidates) == 2
    assert result.metadata.capability_alias == "visual_grounding"
    assert result.metadata.provider_model == "doubao-grounding-provider-v1"
    assert result.metadata.prompt_version == GROUNDING_PROMPT_VERSION
    assert result.metadata.schema_version == GROUNDING_SCHEMA_VERSION
    call = completion.calls[0]
    assert call["model"] == "openai/visual_grounding"
    assert call["api_base"] == "http://litellm:4000/v1"
    assert call["api_key"] == "internal-gateway-key"
    assert call["num_retries"] == 0
    assert "response_format" not in call
    prompt = call["messages"][1]["content"][0]["text"]
    assert "selection_key='whole-look'" in prompt
    assert "(0.100000,0.100000)" in prompt
    assert "<bbox>x1 y1 x2 y2</bbox>" in prompt
    image_url = call["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_litellm_grounder_rejects_invalid_provider_output_without_fake_components() -> None:
    completion = RecordingCompletion("component=shirt; category=tops; confidence=0.9; visible=0.8")
    grounder = LiteLLMVisualGrounder(
        capability_alias="visual_grounding",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=completion,
    )

    with pytest.raises(ProviderError) as error:
        await grounder.ground(image(), scope=selection())

    assert error.value.code == "grounding_schema_invalid"
    assert error.value.retryable is True


@pytest.mark.asyncio
async def test_litellm_grounder_sanitizes_gateway_failure() -> None:
    async def failing_completion(**kwargs: Any) -> object:
        raise ConnectionError("provider leaked secret key sk-sensitive-value")

    grounder = LiteLLMVisualGrounder(
        capability_alias="visual_grounding",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="internal-gateway-key",
        completion=failing_completion,
    )

    with pytest.raises(ProviderError) as error:
        await grounder.ground(image(), scope=selection())

    assert error.value.code == "grounding_unavailable"
    assert "secret" not in error.value.message
    assert error.value.retryable is True
