from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from math import isfinite, sqrt
from typing import Protocol, cast
from urllib.request import Request, urlopen

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.capture.infrastructure.image_data import (
    image_to_jpeg_data_url,
)
from stylecapture_backend.features.capture.processing import (
    EmbeddingResult,
    ProviderError,
)

DOUBAO_MULTIMODAL_EMBEDDING_DIMENSION = 2048


class JsonGateway(Protocol):
    async def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]: ...


class UrllibJsonGateway:
    async def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        return await asyncio.to_thread(
            self._post_json,
            url=url,
            headers=headers,
            payload=payload,
            timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _post_json(
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            decoded = json.load(response)
        if not isinstance(decoded, dict):
            raise TypeError("embedding gateway response must be an object")
        return cast(Mapping[str, object], decoded)


class LiteLLMMultimodalEmbedder:
    def __init__(
        self,
        *,
        model: str,
        gateway_base_url: str,
        gateway_api_key: str,
        gateway: JsonGateway | None = None,
        timeout_seconds: float = 45,
    ) -> None:
        if not model.strip():
            raise ValueError("embedding model must not be empty")
        if not gateway_base_url.strip():
            raise ValueError("embedding gateway base URL must not be empty")
        if not gateway_api_key.strip():
            raise ValueError("embedding gateway API key must not be empty")
        self._model = model
        self._url = f"{gateway_base_url.rstrip('/')}/embeddings/multimodal"
        self._headers = {
            "Authorization": f"Bearer {gateway_api_key}",
            "Content-Type": "application/json",
        }
        self._gateway = gateway or UrllibJsonGateway()
        self._timeout_seconds = timeout_seconds

    async def embed(self, image: ImagePayload) -> EmbeddingResult:
        try:
            response = await self._gateway.post_json(
                url=self._url,
                headers=self._headers,
                payload={
                    "model": self._model,
                    "input": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_to_jpeg_data_url(image)},
                        }
                    ],
                },
                timeout_seconds=self._timeout_seconds,
            )
        except ProviderError:
            raise
        except Exception as error:
            raise ProviderError(
                "embedding_unavailable",
                "Multimodal embedding is temporarily unavailable",
                retryable=True,
            ) from error

        try:
            vector = _embedding_vector(response)
            provider_model = response["model"]
            if not isinstance(provider_model, str) or not provider_model.strip():
                raise TypeError("embedding response model must be text")
            return EmbeddingResult(
                vector=_l2_normalize(vector),
                model_version=provider_model,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError(
                "embedding_schema_invalid",
                "Multimodal embedding returned an invalid vector",
                retryable=False,
            ) from error


def _embedding_vector(response: Mapping[str, object]) -> tuple[float, ...]:
    data = response["data"]
    if isinstance(data, list):
        if len(data) != 1:
            raise ValueError("embedding response must contain exactly one vector")
        data = data[0]
    if not isinstance(data, Mapping):
        raise TypeError("embedding response data must be an object")
    raw = data["embedding"]
    if not isinstance(raw, list):
        raise TypeError("embedding response vector must be a list")
    if raw and isinstance(raw[0], list):
        if len(raw) != 1:
            raise ValueError("embedding response must contain exactly one vector")
        raw = raw[0]
    vector = tuple(float(value) for value in raw)
    if len(vector) != DOUBAO_MULTIMODAL_EMBEDDING_DIMENSION:
        raise ValueError("embedding response has an unexpected dimension")
    if not all(isfinite(value) for value in vector):
        raise ValueError("embedding response contains non-finite values")
    return vector


def _l2_normalize(vector: tuple[float, ...]) -> tuple[float, ...]:
    norm = sqrt(sum(value * value for value in vector))
    if not isfinite(norm) or norm <= 0:
        raise ValueError("embedding response has no usable magnitude")
    return tuple(value / norm for value in vector)
