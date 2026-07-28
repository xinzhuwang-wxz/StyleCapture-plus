from __future__ import annotations

from stylecapture_backend.features.account.infrastructure.repository import (
    SqlAlchemyAccountRepository,
)
from stylecapture_backend.features.capture.infrastructure.fashion_embedding import (
    DisabledImageEmbedder,
    FashionSiglipEmbedder,
)
from stylecapture_backend.features.capture.infrastructure.feed_media import (
    PillowSelectionImageRenderer,
)
from stylecapture_backend.features.capture.infrastructure.grounding import (
    LiteLLMVisualGrounder,
)
from stylecapture_backend.features.capture.infrastructure.hosted_embedding import (
    LiteLLMMultimodalEmbedder,
)
from stylecapture_backend.features.capture.infrastructure.object_store import (
    LocalObjectStore,
    OwnerScopedObjectWriter,
)
from stylecapture_backend.features.capture.infrastructure.providers import LiteLLMVisionTagger
from stylecapture_backend.features.capture.infrastructure.repository import (
    SqlAlchemyCaptureRepository,
)
from stylecapture_backend.features.capture.interfaces.worker import register_capture_task
from stylecapture_backend.features.capture.processing import CaptureProcessor, ImageEmbedder
from stylecapture_backend.features.item_presentation.application import (
    ItemPresentationApplication,
)
from stylecapture_backend.features.item_presentation.infrastructure.repository import (
    SqlAlchemyItemPresentationRepository,
)
from stylecapture_backend.features.item_presentation.interfaces.worker import (
    register_item_presentation_task,
)
from stylecapture_backend.features.item_presentation.processing import (
    ItemPresentationProcessor,
)
from stylecapture_backend.features.look.infrastructure.repository import (
    SqlAlchemyLookRepository,
)
from stylecapture_backend.features.pixel_trial.application import PixelTrialApplication
from stylecapture_backend.features.pixel_trial.infrastructure.repository import (
    SqlAlchemyPixelTrialRepository,
)
from stylecapture_backend.features.pixel_trial.interfaces.worker import (
    register_pixel_trial_task,
)
from stylecapture_backend.features.pixel_trial.processing import PixelTrialProcessor
from stylecapture_backend.features.render.application import RenderApplication
from stylecapture_backend.features.render.infrastructure.collage import (
    PillowLookCollageRenderer,
)
from stylecapture_backend.features.render.infrastructure.providers import (
    FashnTryOnGenerator,
    LiteLLMImageGenerator,
)
from stylecapture_backend.features.render.infrastructure.repository import (
    SqlAlchemyRenderArtifactRepository,
)
from stylecapture_backend.features.render.interfaces.worker import register_render_task
from stylecapture_backend.features.render.processing import RenderProcessor
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.features.wardrobe.infrastructure.repository import (
    SqlAlchemyWardrobeRepository,
)
from stylecapture_backend.platform.celery import build_celery
from stylecapture_backend.platform.config import BackendSettings
from stylecapture_backend.platform.database import build_session_factory
from stylecapture_backend.platform.worker_dependencies import (
    build_outfit_analyzer,
    build_promptable_segmenter,
)

settings = BackendSettings()  # type: ignore[call-arg]
sessions = build_session_factory(
    settings.database_url.get_secret_value(),
    pooled=False,
)
account_repository = SqlAlchemyAccountRepository(sessions)
capture_repository = SqlAlchemyCaptureRepository(
    sessions,
    subject_writes=account_repository,
)
wardrobe_repository = SqlAlchemyWardrobeRepository(
    sessions,
    subject_writes=account_repository,
)
look_repository = SqlAlchemyLookRepository(sessions, subject_writes=account_repository)
render_repository = SqlAlchemyRenderArtifactRepository(
    sessions,
    subject_writes=account_repository,
)
pixel_trial_repository = SqlAlchemyPixelTrialRepository(
    sessions,
    subject_writes=account_repository,
)
item_presentation_repository = SqlAlchemyItemPresentationRepository(
    sessions,
    subject_writes=account_repository,
)
object_store = LocalObjectStore(
    root=settings.upload_root,
    signing_secret=settings.upload_signing_secret.get_secret_value(),
    public_upload_prefix=settings.public_upload_prefix,
    max_upload_bytes=settings.max_upload_bytes,
    max_image_pixels=settings.max_image_pixels,
)
owner_scoped_objects = OwnerScopedObjectWriter(
    objects=object_store,
    subject_writes=account_repository,
)
vision = LiteLLMVisionTagger(
    capability_alias=settings.vision_model_alias,
    gateway_base_url=settings.litellm_base_url,
    gateway_api_key=settings.litellm_api_key.get_secret_value(),
)
grounder = LiteLLMVisualGrounder(
    capability_alias=settings.grounding_model_alias,
    gateway_base_url=settings.litellm_base_url,
    gateway_api_key=settings.litellm_api_key.get_secret_value(),
)
outfit_analyzer = build_outfit_analyzer(settings)
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
    segmenter=build_promptable_segmenter(settings),
    selection_images=PillowSelectionImageRenderer(),
    display_assets=owner_scoped_objects,
    looks=look_repository,
    grounder=grounder,
    outfit_analyzer=outfit_analyzer,
)
celery = build_celery(settings.redis_url.get_secret_value())
capture_task = register_capture_task(
    celery,
    processor,
    max_retries=settings.worker_max_retries,
)
render_processor = RenderProcessor(
    artifacts=render_repository,
    renders=RenderApplication(artifacts=render_repository),
    looks=look_repository,
    wardrobe=wardrobe_repository,
    objects=owner_scoped_objects,
    collages=PillowLookCollageRenderer(),
    pixel_generator=LiteLLMImageGenerator(
        capability_alias=settings.image_generation_model_alias,
        gateway_base_url=settings.litellm_base_url,
        gateway_api_key=settings.litellm_api_key.get_secret_value(),
        timeout_seconds=settings.render_request_timeout_seconds,
        download_max_bytes=settings.render_download_max_bytes,
    ),
    try_on_generator=FashnTryOnGenerator(
        api_base_url=settings.fashn_api_base,
        api_key=settings.fashn_api_key.get_secret_value(),
        timeout_seconds=settings.render_request_timeout_seconds,
        poll_interval_seconds=settings.render_poll_interval_seconds,
        poll_timeout_seconds=settings.render_poll_timeout_seconds,
    ),
    fixed_model_object_key=settings.fixed_model_object_key,
)
render_task = register_render_task(
    celery,
    render_processor,
    max_retries=settings.worker_max_retries,
)
pixel_trial_processor = PixelTrialProcessor(
    trials=PixelTrialApplication(trials=pixel_trial_repository),
    objects=owner_scoped_objects,
    generator=LiteLLMImageGenerator(
        capability_alias=settings.image_generation_model_alias,
        gateway_base_url=settings.litellm_base_url,
        gateway_api_key=settings.litellm_api_key.get_secret_value(),
        timeout_seconds=settings.render_request_timeout_seconds,
        download_max_bytes=settings.render_download_max_bytes,
    ),
)
pixel_trial_task = register_pixel_trial_task(
    celery,
    pixel_trial_processor,
    max_retries=settings.worker_max_retries,
)
item_presentation_processor = ItemPresentationProcessor(
    presentations=ItemPresentationApplication(
        assets=item_presentation_repository,
        wardrobe=WardrobeApplication(wardrobe=wardrobe_repository, sources=object_store),
    ),
    wardrobe=WardrobeApplication(wardrobe=wardrobe_repository, sources=object_store),
    objects=owner_scoped_objects,
    generator=LiteLLMImageGenerator(
        capability_alias=settings.image_generation_model_alias,
        gateway_base_url=settings.litellm_base_url,
        gateway_api_key=settings.litellm_api_key.get_secret_value(),
        timeout_seconds=settings.render_request_timeout_seconds,
        download_max_bytes=settings.render_download_max_bytes,
    ),
)
item_presentation_task = register_item_presentation_task(
    celery,
    item_presentation_processor,
    max_retries=settings.worker_max_retries,
)
