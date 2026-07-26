from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from PIL import Image
from pillow_heif import from_pillow
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    ImagePayload,
    NormalizedPoint,
    OwnershipState,
)
from stylecapture_backend.features.capture.ports import StoredObject
from stylecapture_backend.features.look.domain import Look, LookComponent, LookDetail
from stylecapture_backend.features.render.application import RenderApplication
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderArtifactStatus,
    RenderInputSignature,
    RenderPrivacy,
    RenderProviderTrace,
)
from stylecapture_backend.features.render.infrastructure.collage import (
    PillowLookCollageRenderer,
)
from stylecapture_backend.features.render.infrastructure.providers import GeneratedImage
from stylecapture_backend.features.render.processing import RenderProcessor
from stylecapture_backend.features.wardrobe.domain import ItemStatus, WardrobeItem


class MemoryRenderRepository:
    def __init__(self, artifacts: list[RenderArtifact]) -> None:
        self.artifacts = {artifact.id: artifact for artifact in artifacts}

    async def ensure_requested(self, artifact: RenderArtifact) -> RenderArtifact:
        self.artifacts.setdefault(artifact.id, artifact)
        return self.artifacts[artifact.id]

    async def save(self, artifact: RenderArtifact) -> RenderArtifact:
        self.artifacts[artifact.id] = artifact
        return artifact

    async def find_cache_hit(
        self,
        *,
        look_id: UUID,
        kind: RenderArtifactKind,
        input_signature: RenderInputSignature,
    ) -> RenderArtifact | None:
        return None

    async def list_for_look(self, *, user_id: UUID, look_id: UUID) -> list[RenderArtifact]:
        return [
            artifact
            for artifact in self.artifacts.values()
            if artifact.user_id == user_id and artifact.look_id == look_id
        ]

    async def get_for_user(
        self,
        *,
        user_id: UUID,
        artifact_id: UUID,
    ) -> RenderArtifact | None:
        artifact = self.artifacts.get(artifact_id)
        return artifact if artifact is not None and artifact.user_id == user_id else None


class MemoryLookRepository:
    def __init__(self, detail: LookDetail) -> None:
        self.detail = detail

    async def get_detail_for_user(self, look_id: UUID, user_id: UUID) -> LookDetail | None:
        if self.detail.look.id == look_id and self.detail.look.user_id == user_id:
            return self.detail
        return None


class MemoryWardrobeRepository:
    def __init__(self, *items: WardrobeItem) -> None:
        self.items = {item.id: item for item in items}

    async def get_for_user(self, item_id: UUID, user_id: UUID) -> WardrobeItem | None:
        item = self.items.get(item_id)
        return item if item is not None and item.user_id == user_id else None


class MemoryObjectStore:
    def __init__(self, images: dict[str, ImagePayload]) -> None:
        self.images = images

    def describe(self, object_key: str) -> StoredObject:
        image = self.images[object_key]
        return StoredObject(
            owner_id=None,
            object_key=object_key,
            content_type=image.content_type,
            byte_size=len(image.body),
            sha256=image.sha256,
            width=64,
            height=96,
        )

    def read_image(self, object_key: str) -> ImagePayload:
        return self.images[object_key]

    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload:
        stored = ImagePayload(
            object_key=f"{prefix}/{image.sha256}.png",
            content_type=image.content_type,
            body=image.body,
            sha256=image.sha256,
        )
        self.images[stored.object_key] = stored
        return stored


class SuccessfulPixelGenerator:
    def __init__(self) -> None:
        self.images: tuple[ImagePayload, ...] = ()
        self.prompt = ""
        self.size = ""

    async def generate(
        self,
        *,
        prompt: str,
        images: tuple[ImagePayload, ...],
        size: str = "1024x1024",
    ) -> GeneratedImage:
        self.prompt = prompt
        self.images = images
        self.size = size
        body = png((180, 90, 255))
        return GeneratedImage(
            body=body,
            content_type="image/png",
            sha256=sha256(body).hexdigest(),
            provider_trace=RenderProviderTrace(
                provider="test-private",
                model="test-private-model",
                parameters={"size": size, "image_count": len(images)},
            ),
        )


class SuccessfulTryOnGenerator:
    def __init__(self) -> None:
        self.categories: list[str] = []

    async def try_on(
        self,
        *,
        model_image: ImagePayload,
        garment_image: ImagePayload,
        category: str = "auto",
        mode: str = "balanced",
    ) -> GeneratedImage:
        self.categories.append(category)
        body = png((90, 140, 220))
        return GeneratedImage(
            body=body,
            content_type="image/png",
            sha256=sha256(body).hexdigest(),
            provider_trace=RenderProviderTrace(
                provider="test-try-on",
                model="test-try-on-model",
                parameters={"category": category, "mode": mode},
            ),
        )


class CorruptPixelGenerator:
    async def generate(
        self,
        *,
        prompt: str,
        images: tuple[ImagePayload, ...],
        size: str = "1024x1024",
    ) -> GeneratedImage:
        body = png((220, 30, 80))
        return GeneratedImage(
            body=body,
            content_type="image/png",
            sha256="0" * 64,
            provider_trace=RenderProviderTrace(
                provider="corrupt-test",
                model="corrupt-test-model",
                parameters={},
            ),
        )


def png(color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 96), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def payload(key: str, color: tuple[int, int, int]) -> ImagePayload:
    body = png(color)
    return ImagePayload(
        object_key=key,
        content_type="image/png",
        body=body,
        sha256=sha256(body).hexdigest(),
    )


def heic_payload(key: str, color: tuple[int, int, int]) -> ImagePayload:
    buffer = BytesIO()
    from_pillow(Image.new("RGB", (64, 96), color=color)).save(buffer, format="HEIF")
    body = buffer.getvalue()
    return ImagePayload(
        object_key=key,
        content_type="image/heic",
        body=body,
        sha256=sha256(body).hexdigest(),
    )


def fixture() -> tuple[UUID, LookDetail, WardrobeItem, MemoryObjectStore]:
    user_id = uuid4()
    source = payload("originals/feed/look.png", (240, 220, 230))
    item_image = payload("derived/items/top.png", (250, 50, 100))
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.FEED,
            object_key=source.object_key,
            sha256=source.sha256,
        ),
        ownership=OwnershipState.INSPIRATION,
    )
    look = Look.feed_saved(
        user_id=user_id,
        capture_id=capture.id,
        source_selection_key="whole",
    )
    item = (
        WardrobeItem.processing(capture, selection_key="top")
        .with_display_object(item_image.object_key)
        .with_status(ItemStatus.READY)
    )
    component = LookComponent.pending(
        look_id=look.id,
        component_key="top",
        evidence_region=(
            NormalizedPoint(0.1, 0.1),
            NormalizedPoint(0.8, 0.1),
            NormalizedPoint(0.8, 0.8),
        ),
        confidence=0.9,
        grounding_metadata={"source": "test"},
        role="tops",
    ).with_item(item.id)
    return (
        user_id,
        LookDetail(look=look, components=(component,), preference_signals=()),
        item,
        MemoryObjectStore({source.object_key: source, item_image.object_key: item_image}),
    )


def add_component(
    detail: LookDetail,
    item: WardrobeItem,
    objects: MemoryObjectStore,
    *,
    role: str,
    selection_key: str,
    color: tuple[int, int, int],
) -> tuple[LookDetail, WardrobeItem]:
    item_image = payload(f"derived/items/{selection_key}.png", color)
    objects.images[item_image.object_key] = item_image
    added_item = replace(
        item,
        id=uuid4(),
        selection_key=selection_key,
        display_object_key=item_image.object_key,
    )
    component = LookComponent.pending(
        look_id=detail.look.id,
        component_key=selection_key,
        evidence_region=(
            NormalizedPoint(0.1, 0.1),
            NormalizedPoint(0.8, 0.1),
            NormalizedPoint(0.8, 0.8),
        ),
        confidence=0.9,
        grounding_metadata={"source": "test"},
        role=role,
        display_order=len(detail.components),
    ).with_item(added_item.id)
    return (
        LookDetail(
            look=detail.look,
            components=(*detail.components, component),
            preference_signals=detail.preference_signals,
        ),
        added_item,
    )


def queued(
    *,
    user_id: UUID,
    look_id: UUID,
    kind: RenderArtifactKind,
    request_key: str,
    source_artifact_id: UUID | None = None,
    subject_object_key: str | None = None,
) -> RenderArtifact:
    return RenderArtifact.queued(
        user_id=user_id,
        look_id=look_id,
        kind=kind,
        input_signature=RenderInputSignature(
            version="look-render-v1",
            hash=sha256(f"{kind}:{request_key}".encode()).hexdigest(),
        ),
        request_key=request_key,
        source_artifact_id=source_artifact_id,
        subject_object_key=subject_object_key,
        privacy=(
            RenderPrivacy.SHAREABLE_PIXEL
            if kind is RenderArtifactKind.PIXEL_COVER
            else RenderPrivacy.PRIVATE
        ),
    )


@pytest.mark.asyncio
async def test_processor_builds_real_collage_and_pixel_cover() -> None:
    user_id, detail, item, objects = fixture()
    look_source = objects.images["originals/feed/look.png"]
    detail = replace(
        detail,
        look=detail.look.with_display_object(look_source.object_key),
    )
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage",
    )
    pixel = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.PIXEL_COVER,
        request_key="pixel",
        source_artifact_id=collage.id,
    )
    repository = MemoryRenderRepository([collage, pixel])
    renders = RenderApplication(artifacts=repository)
    pixel_generator = SuccessfulPixelGenerator()
    processor = RenderProcessor(
        artifacts=repository,
        renders=renders,
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=pixel_generator,
        try_on_generator=None,
        fixed_model_object_key=None,
    )

    await processor.process(user_id=user_id, artifact_id=collage.id)
    await processor.process(user_id=user_id, artifact_id=pixel.id)

    stored_collage = repository.artifacts[collage.id]
    stored_pixel = repository.artifacts[pixel.id]
    assert stored_collage.status is RenderArtifactStatus.SUCCEEDED
    assert stored_collage.output is not None
    assert stored_pixel.status is RenderArtifactStatus.SUCCEEDED
    assert stored_pixel.output is not None
    assert stored_pixel.share_eligible is True
    assert stored_pixel.provider_trace is not None
    assert stored_pixel.provider_trace.provider == "test-private"
    assert stored_pixel.provider_trace.parameters["capability_id"] == "look.pixel_cover"
    assert stored_pixel.provider_trace.parameters["capability_alias"] == "image_generation"
    assert stored_pixel.provider_trace.parameters["prompt_version"] == "look-pixel-cover-zh-v4"
    assert "6-10px" in pixel_generator.prompt
    assert "3:4" in pixel_generator.prompt
    assert "1:1" in pixel_generator.prompt
    assert "不要复刻完整房间" in pixel_generator.prompt
    assert stored_pixel.provider_trace.parameters["schema_version"] == "generated-image-v1"
    assert len(pixel_generator.images) == 2
    assert pixel_generator.size == "1536x2048"
    assert pixel_generator.images[0].object_key == look_source.object_key


@pytest.mark.asyncio
async def test_pixel_cover_converts_heic_look_source_before_render_provider() -> None:
    user_id, detail, item, objects = fixture()
    look_source = heic_payload("originals/upload/look.heic", (220, 220, 240))
    objects.images[look_source.object_key] = look_source
    detail = replace(
        detail,
        look=detail.look.with_display_object(look_source.object_key),
    )
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage",
    )
    pixel = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.PIXEL_COVER,
        request_key="pixel",
        source_artifact_id=collage.id,
    )
    repository = MemoryRenderRepository([collage, pixel])
    pixel_generator = SuccessfulPixelGenerator()
    processor = RenderProcessor(
        artifacts=repository,
        renders=RenderApplication(artifacts=repository),
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=pixel_generator,
        try_on_generator=None,
        fixed_model_object_key=None,
    )

    await processor.process(user_id=user_id, artifact_id=collage.id)
    await processor.process(user_id=user_id, artifact_id=pixel.id)

    assert repository.artifacts[pixel.id].status is RenderArtifactStatus.SUCCEEDED
    assert pixel_generator.images[0].content_type == "image/jpeg"
    assert pixel_generator.images[0].object_key.endswith(".render-input.jpg")


@pytest.mark.asyncio
async def test_missing_pixel_provider_degrades_to_non_shareable_collage() -> None:
    user_id, detail, item, objects = fixture()
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage",
    )
    repository = MemoryRenderRepository([collage])
    renders = RenderApplication(artifacts=repository)
    processor = RenderProcessor(
        artifacts=repository,
        renders=renders,
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=None,
        try_on_generator=None,
        fixed_model_object_key=None,
    )
    await processor.process(user_id=user_id, artifact_id=collage.id)
    pixel = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.PIXEL_COVER,
        request_key="pixel",
        source_artifact_id=collage.id,
    )
    repository.artifacts[pixel.id] = pixel

    await processor.process(user_id=user_id, artifact_id=pixel.id)

    stored = repository.artifacts[pixel.id]
    assert stored.status is RenderArtifactStatus.DEGRADED
    assert stored.fallback_artifact_id == collage.id
    assert stored.share_eligible is False


@pytest.mark.asyncio
async def test_fixed_model_try_on_uses_supported_garment_roles() -> None:
    user_id, detail, item, objects = fixture()
    model = payload("derived/models/fixed.png", (200, 180, 170))
    objects.images[model.object_key] = model
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage",
    )
    repository = MemoryRenderRepository([collage])
    renders = RenderApplication(artifacts=repository)
    try_on = SuccessfulTryOnGenerator()
    processor = RenderProcessor(
        artifacts=repository,
        renders=renders,
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=None,
        try_on_generator=try_on,
        fixed_model_object_key=model.object_key,
    )
    await processor.process(user_id=user_id, artifact_id=collage.id)
    artifact = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.TRY_ON,
        request_key="try-on",
        source_artifact_id=collage.id,
    )
    repository.artifacts[artifact.id] = artifact

    await processor.process(user_id=user_id, artifact_id=artifact.id)

    stored = repository.artifacts[artifact.id]
    assert stored.status is RenderArtifactStatus.SUCCEEDED
    assert stored.share_eligible is False
    assert try_on.categories == ["tops"]
    assert stored.provider_trace is not None
    assert stored.provider_trace.parameters["personalization"] == "fixed_model"
    assert stored.provider_trace.parameters["capability_id"] == "look.virtual_try_on"
    assert stored.provider_trace.parameters["capability_alias"] == "specialized_try_on"
    assert stored.provider_trace.parameters["prompt_version"] == "not_applicable"


@pytest.mark.parametrize("second_role", ["bottoms", "shoes", "accessories"])
@pytest.mark.asyncio
async def test_fixed_model_complete_look_uses_multimodal_image_edit(
    second_role: str,
) -> None:
    user_id, detail, item, objects = fixture()
    detail, second_item = add_component(
        detail,
        item,
        objects,
        role=second_role,
        selection_key=f"second_{second_role}",
        color=(40, 90, 180),
    )
    model = payload("derived/models/fixed.png", (200, 180, 170))
    objects.images[model.object_key] = model
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage",
    )
    repository = MemoryRenderRepository([collage])
    renders = RenderApplication(artifacts=repository)
    dedicated_try_on = SuccessfulTryOnGenerator()
    processor = RenderProcessor(
        artifacts=repository,
        renders=renders,
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item, second_item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=SuccessfulPixelGenerator(),
        try_on_generator=dedicated_try_on,
        fixed_model_object_key=model.object_key,
    )
    await processor.process(user_id=user_id, artifact_id=collage.id)
    artifact = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.TRY_ON,
        request_key=f"fixed-complete-{second_role}",
        source_artifact_id=collage.id,
    )
    repository.artifacts[artifact.id] = artifact

    await processor.process(user_id=user_id, artifact_id=artifact.id)

    stored = repository.artifacts[artifact.id]
    assert stored.status is RenderArtifactStatus.SUCCEEDED
    assert stored.provider_trace is not None
    assert stored.provider_trace.parameters["personalization"] == "fixed_model"
    assert stored.provider_trace.parameters["strategy"] == "multimodal_image_edit"
    assert stored.provider_trace.parameters["capability_id"] == "look.virtual_try_on"
    assert stored.provider_trace.parameters["capability_alias"] == "image_generation"
    assert stored.provider_trace.parameters["prompt_version"] == "look-virtual-try-on-zh-v2"
    assert stored.provider_trace.parameters["schema_version"] == "generated-image-v1"
    assert stored.provider_trace.parameters["image_count"] == 3
    assert stored.provider_trace.parameters["garment_count"] == 2
    assert dedicated_try_on.categories == []


@pytest.mark.asyncio
async def test_fixed_model_dedicated_try_on_degrades_when_look_coverage_is_incomplete() -> None:
    user_id, detail, item, objects = fixture()
    detail, shoes = add_component(
        detail,
        item,
        objects,
        role="shoes",
        selection_key="shoes",
        color=(40, 90, 180),
    )
    model = payload("derived/models/fixed.png", (200, 180, 170))
    objects.images[model.object_key] = model
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage",
    )
    repository = MemoryRenderRepository([collage])
    renders = RenderApplication(artifacts=repository)
    dedicated_try_on = SuccessfulTryOnGenerator()
    processor = RenderProcessor(
        artifacts=repository,
        renders=renders,
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item, shoes),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=None,
        try_on_generator=dedicated_try_on,
        fixed_model_object_key=model.object_key,
    )
    await processor.process(user_id=user_id, artifact_id=collage.id)
    artifact = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.TRY_ON,
        request_key="fixed-incomplete",
        source_artifact_id=collage.id,
    )
    repository.artifacts[artifact.id] = artifact

    await processor.process(user_id=user_id, artifact_id=artifact.id)

    stored = repository.artifacts[artifact.id]
    assert stored.status is RenderArtifactStatus.DEGRADED
    assert stored.fallback_artifact_id == collage.id
    assert stored.failure_message is not None
    assert "无法完整覆盖" in stored.failure_message
    assert dedicated_try_on.categories == []


@pytest.mark.asyncio
async def test_personal_try_on_uses_uploaded_subject_and_real_image_provider_fallback() -> None:
    user_id, detail, item, objects = fixture()
    subject = payload("originals/upload/my-full-body.png", (160, 130, 110))
    objects.images[subject.object_key] = subject
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage",
    )
    repository = MemoryRenderRepository([collage])
    renders = RenderApplication(artifacts=repository)
    dedicated_try_on = SuccessfulTryOnGenerator()
    processor = RenderProcessor(
        artifacts=repository,
        renders=renders,
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=SuccessfulPixelGenerator(),
        try_on_generator=dedicated_try_on,
        fixed_model_object_key=None,
    )
    await processor.process(user_id=user_id, artifact_id=collage.id)
    artifact = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.TRY_ON,
        request_key="personal-try-on",
        source_artifact_id=collage.id,
        subject_object_key=subject.object_key,
    )
    repository.artifacts[artifact.id] = artifact

    await processor.process(user_id=user_id, artifact_id=artifact.id)

    stored = repository.artifacts[artifact.id]
    assert stored.status is RenderArtifactStatus.SUCCEEDED
    assert stored.subject_object_key == subject.object_key
    assert stored.provider_trace is not None
    assert stored.provider_trace.parameters["personalization"] == "user_photo"
    assert stored.provider_trace.parameters["strategy"] == "multimodal_image_edit"
    assert stored.provider_trace.parameters["capability_id"] == "look.virtual_try_on"
    assert stored.provider_trace.parameters["prompt_version"] == "look-virtual-try-on-zh-v2"
    assert stored.provider_trace.parameters["image_count"] == 2
    assert dedicated_try_on.categories == []


@pytest.mark.asyncio
async def test_corrupt_pixel_provider_output_degrades_without_getting_stuck() -> None:
    user_id, detail, item, objects = fixture()
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage",
    )
    repository = MemoryRenderRepository([collage])
    renders = RenderApplication(artifacts=repository)
    processor = RenderProcessor(
        artifacts=repository,
        renders=renders,
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=CorruptPixelGenerator(),
        try_on_generator=None,
        fixed_model_object_key=None,
    )
    await processor.process(user_id=user_id, artifact_id=collage.id)
    pixel = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.PIXEL_COVER,
        request_key="pixel",
        source_artifact_id=collage.id,
    )
    repository.artifacts[pixel.id] = pixel

    await processor.process(user_id=user_id, artifact_id=pixel.id)

    stored = repository.artifacts[pixel.id]
    assert stored.status is RenderArtifactStatus.DEGRADED
    assert stored.fallback_artifact_id == collage.id
    assert stored.share_eligible is False
