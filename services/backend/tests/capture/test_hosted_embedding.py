from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO

import pytest
from PIL import Image
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.capture.infrastructure.hosted_embedding import (
    DOUBAO_MULTIMODAL_EMBEDDING_DIMENSION,
    LiteLLMMultimodalEmbedder,
)
from stylecapture_backend.features.capture.processing import ProviderError


class RecordingGateway:
    def __init__(self, response: Mapping[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "payload": dict(payload),
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.response


def image() -> ImagePayload:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), (30, 60, 90)).save(buffer, format="PNG")
    return ImagePayload(
        object_key="originals/item.png",
        content_type="image/png",
        body=buffer.getvalue(),
        sha256="a" * 64,
    )


def test_litellm_embedding_requires_a_gateway_credential() -> None:
    with pytest.raises(ValueError, match="API key"):
        LiteLLMMultimodalEmbedder(
            model="doubao-embedding-vision-250615",
            gateway_base_url="http://litellm:4000/v1",
            gateway_api_key=" ",
        )


@pytest.mark.asyncio
async def test_litellm_embedding_normalizes_the_real_multimodal_response() -> None:
    raw_vector = [0.0] * DOUBAO_MULTIMODAL_EMBEDDING_DIMENSION
    raw_vector[0] = 2.0
    gateway = RecordingGateway(
        {
            "model": "doubao-embedding-vision-250615",
            "data": {
                "object": "embedding",
                "embedding": raw_vector,
            },
        }
    )
    embedder = LiteLLMMultimodalEmbedder(
        model="doubao-embedding-vision-250615",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="gateway-secret",
        gateway=gateway,
    )

    result = await embedder.embed(image())

    assert result.model_version == "doubao-embedding-vision-250615"
    assert len(result.vector) == DOUBAO_MULTIMODAL_EMBEDDING_DIMENSION
    assert result.vector[0] == 1.0
    assert all(value == 0.0 for value in result.vector[1:])
    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    assert call["url"] == "http://litellm:4000/v1/embeddings/multimodal"
    assert call["headers"] == {
        "Authorization": "Bearer gateway-secret",
        "Content-Type": "application/json",
    }
    payload = call["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "doubao-embedding-vision-250615"
    assert isinstance(payload["input"], list)
    image_input = payload["input"][0]
    assert isinstance(image_input, dict)
    assert image_input["type"] == "image_url"
    assert image_input["image_url"]["url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_litellm_embedding_rejects_an_unexpected_provider_dimension() -> None:
    gateway = RecordingGateway(
        {
            "model": "doubao-embedding-vision-250615",
            "data": {
                "object": "embedding",
                "embedding": [1.0, 0.0],
            },
        }
    )
    embedder = LiteLLMMultimodalEmbedder(
        model="doubao-embedding-vision-250615",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="gateway-secret",
        gateway=gateway,
    )

    with pytest.raises(ProviderError) as error:
        await embedder.embed(image())

    assert error.value.code == "embedding_schema_invalid"
    assert error.value.retryable is False
