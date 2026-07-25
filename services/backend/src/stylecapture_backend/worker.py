from __future__ import annotations

from stylecapture_backend.features.capture.infrastructure.fashion_embedding import (
    DisabledImageEmbedder,
    FashionSiglipEmbedder,
)
from stylecapture_backend.features.capture.infrastructure.feed_media import (
    CoarsePolygonSegmentationProvider,
    PillowSelectionImageRenderer,
)
from stylecapture_backend.features.capture.infrastructure.hosted_embedding import (
    LiteLLMMultimodalEmbedder,
)
from stylecapture_backend.features.capture.infrastructure.object_store import LocalObjectStore
from stylecapture_backend.features.capture.infrastructure.providers import LiteLLMVisionTagger
from stylecapture_backend.features.capture.infrastructure.repository import (
    SqlAlchemyCaptureRepository,
)
from stylecapture_backend.features.capture.interfaces.worker import register_capture_task
from stylecapture_backend.features.capture.processing import CaptureProcessor, ImageEmbedder
from stylecapture_backend.features.wardrobe.infrastructure.repository import (
    SqlAlchemyWardrobeRepository,
)
from stylecapture_backend.platform.celery import build_celery
from stylecapture_backend.platform.config import BackendSettings
from stylecapture_backend.platform.database import build_session_factory

settings = BackendSettings()  # type: ignore[call-arg]
sessions = build_session_factory(
    settings.database_url.get_secret_value(),
    pooled=False,
)
capture_repository = SqlAlchemyCaptureRepository(sessions)
wardrobe_repository = SqlAlchemyWardrobeRepository(sessions)
object_store = LocalObjectStore(
    root=settings.upload_root,
    signing_secret=settings.upload_signing_secret.get_secret_value(),
    public_upload_prefix=settings.public_upload_prefix,
    max_upload_bytes=settings.max_upload_bytes,
    max_image_pixels=settings.max_image_pixels,
)
vision = LiteLLMVisionTagger(
    capability_alias=settings.vision_model_alias,
    gateway_base_url=settings.litellm_base_url,
    gateway_api_key=settings.litellm_api_key.get_secret_value(),
)
embedder: ImageEmbedder
if settings.embedding_mode == "hosted":
    embedder = LiteLLMMultimodalEmbedder(
        model=settings.embedding_model,
        gateway_base_url=settings.litellm_base_url,
        gateway_api_key=settings.litellm_api_key.get_secret_value(),
    )
elif settings.embedding_mode == "fashion_siglip":
    embedder = FashionSiglipEmbedder(device=settings.embedding_device)
else:
    embedder = DisabledImageEmbedder()
processor = CaptureProcessor(
    captures=capture_repository,
    jobs=capture_repository,
    wardrobe=wardrobe_repository,
    objects=object_store,
    vision=vision,
    embedder=embedder,
    segmenter=CoarsePolygonSegmentationProvider(),
    selection_images=PillowSelectionImageRenderer(),
    display_assets=object_store,
)
celery = build_celery(settings.redis_url.get_secret_value())
capture_task = register_capture_task(
    celery,
    processor,
    max_retries=settings.worker_max_retries,
)
