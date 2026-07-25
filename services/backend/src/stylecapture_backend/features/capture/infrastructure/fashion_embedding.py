from __future__ import annotations

import asyncio
from collections.abc import Callable
from io import BytesIO
from threading import Lock
from typing import Protocol

from PIL import Image

from stylecapture_backend.features.capture.processing import (
    EmbeddingResult,
    ImagePayload,
    ProviderError,
)

FASHION_SIGLIP_MODEL_ID = "Marqo/marqo-fashionSigLIP"
FASHION_SIGLIP_REVISION = "c56244cc94f92419e8369fa71efdaf403b124ce8"
FASHION_SIGLIP_DIMENSION = 768


class FashionEmbeddingBackend(Protocol):
    def encode(self, image: ImagePayload) -> tuple[float, ...]: ...


class FashionSiglipEmbedder:
    def __init__(
        self,
        *,
        backend_factory: Callable[[], FashionEmbeddingBackend] | None = None,
        device: str = "cpu",
    ) -> None:
        self._backend_factory = backend_factory or (
            lambda: TransformersFashionSiglipBackend(device=device)
        )
        self._backend: FashionEmbeddingBackend | None = None
        self._load_lock = Lock()

    async def embed(self, image: ImagePayload) -> EmbeddingResult:
        try:
            vector = await asyncio.to_thread(self._encode, image)
        except Exception as error:
            raise ProviderError(
                "embedding_unavailable",
                "Fashion embedding is temporarily unavailable",
                retryable=True,
            ) from error
        try:
            if len(vector) != FASHION_SIGLIP_DIMENSION:
                raise ValueError("FashionSigLIP returned an unexpected dimension")
            return EmbeddingResult(
                vector=vector,
                model_version=f"{FASHION_SIGLIP_MODEL_ID}@{FASHION_SIGLIP_REVISION}",
            )
        except ValueError as error:
            raise ProviderError(
                "embedding_schema_invalid",
                "Fashion embedding returned an invalid vector",
                retryable=False,
            ) from error

    def _encode(self, image: ImagePayload) -> tuple[float, ...]:
        return self._backend_instance().encode(image)

    def _backend_instance(self) -> FashionEmbeddingBackend:
        if self._backend is not None:
            return self._backend
        with self._load_lock:
            if self._backend is None:
                self._backend = self._backend_factory()
        return self._backend


class DisabledImageEmbedder:
    async def embed(self, image: ImagePayload) -> EmbeddingResult:
        raise ProviderError(
            "embedding_capability_disabled",
            "Fashion embedding is disabled in this worker profile",
            retryable=False,
        )


class TransformersFashionSiglipBackend:
    def __init__(self, *, device: str) -> None:
        import torch  # type: ignore[import-not-found]
        from transformers import AutoModel, AutoProcessor  # type: ignore[import-not-found]

        self._torch = torch
        self._device = device
        self._processor = AutoProcessor.from_pretrained(
            FASHION_SIGLIP_MODEL_ID,
            revision=FASHION_SIGLIP_REVISION,
            trust_remote_code=True,
        )
        self._model = AutoModel.from_pretrained(
            FASHION_SIGLIP_MODEL_ID,
            revision=FASHION_SIGLIP_REVISION,
            trust_remote_code=True,
            use_safetensors=True,
        ).to(device)
        self._model.eval()

    def encode(self, image: ImagePayload) -> tuple[float, ...]:
        with Image.open(BytesIO(image.body)) as source:
            rendered = source.convert("RGB")
        processed = self._processor(images=[rendered], return_tensors="pt")
        pixel_values = processed["pixel_values"].to(self._device)
        with self._torch.inference_mode():
            features = self._model.get_image_features(pixel_values, normalize=True)
        return tuple(float(value) for value in features[0].float().cpu().tolist())
