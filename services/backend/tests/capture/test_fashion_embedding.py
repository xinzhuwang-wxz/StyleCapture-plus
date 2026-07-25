import pytest
from stylecapture_backend.features.capture.infrastructure.fashion_embedding import (
    FASHION_SIGLIP_MODEL_ID,
    FASHION_SIGLIP_REVISION,
    FashionSiglipEmbedder,
    TransformersFashionSiglipBackend,
)
from stylecapture_backend.features.capture.processing import ImagePayload, ProviderError


class RecordingBackend:
    def __init__(
        self,
        vector: tuple[float, ...] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.vector = vector
        self.error = error
        self.calls = 0

    def encode(self, image: ImagePayload) -> tuple[float, ...]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.vector is not None
        return self.vector


def image() -> ImagePayload:
    return ImagePayload(
        object_key="originals/item.png",
        content_type="image/png",
        body=b"validated-image",
        sha256="a" * 64,
    )


@pytest.mark.asyncio
async def test_fashion_siglip_loads_lazily_and_reuses_the_pinned_backend() -> None:
    backend = RecordingBackend(vector=(1.0,) + (0.0,) * 767)
    factory_calls = 0

    def factory() -> RecordingBackend:
        nonlocal factory_calls
        factory_calls += 1
        return backend

    embedder = FashionSiglipEmbedder(backend_factory=factory)
    assert factory_calls == 0

    first = await embedder.embed(image())
    second = await embedder.embed(image())

    assert factory_calls == 1
    assert backend.calls == 2
    assert first == second
    assert first.model_version == f"{FASHION_SIGLIP_MODEL_ID}@{FASHION_SIGLIP_REVISION}"


@pytest.mark.asyncio
async def test_fashion_siglip_rejects_wrong_dimension_without_synthetic_padding() -> None:
    backend = RecordingBackend(vector=(1.0, 0.0))
    embedder = FashionSiglipEmbedder(backend_factory=lambda: backend)

    with pytest.raises(ProviderError) as error:
        await embedder.embed(image())

    assert error.value.code == "embedding_schema_invalid"
    assert error.value.retryable is False


@pytest.mark.asyncio
async def test_fashion_siglip_sanitizes_backend_failure() -> None:
    backend = RecordingBackend(error=RuntimeError("private model path /secrets/model failed"))

    def factory() -> RecordingBackend:
        return backend

    embedder = FashionSiglipEmbedder(backend_factory=factory)

    with pytest.raises(ProviderError) as error:
        await embedder.embed(image())

    assert error.value.code == "embedding_unavailable"
    assert "private" not in error.value.message
    assert error.value.retryable is True


def test_transformers_fashion_siglip_local_backend_is_disabled_without_remote_code() -> None:
    # Catches: loading a Hugging Face repo with executable remote code in ai-light.
    # The product default is hosted embedding via LiteLLM.
    with pytest.raises(RuntimeError, match="disabled"):
        TransformersFashionSiglipBackend(device="cpu")
