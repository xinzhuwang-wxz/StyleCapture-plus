from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
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
from stylecapture_backend.features.item_presentation.application import ItemPresentationView
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationKind,
    ItemPresentationStatus,
)
from stylecapture_backend.features.look.domain import Look, LookComponent, LookDetail
from stylecapture_backend.features.render.application import RenderApplication
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderArtifactStatus,
    RenderInputSignature,
    RenderOutput,
    RenderPrivacy,
    RenderProviderTrace,
)
from stylecapture_backend.features.render.infrastructure.collage import (
    PillowLookCollageRenderer,
)
from stylecapture_backend.features.render.infrastructure.providers import (
    GeneratedImage,
    RenderProviderError,
)
from stylecapture_backend.features.render.processing import RenderProcessor, RetryableRenderError
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

    async def claim_queued_for_recovery(
        self,
        *,
        user_id: UUID,
        artifact_id: UUID,
        stale_before: datetime,
    ) -> RenderArtifact | None:
        artifact = self.artifacts.get(artifact_id)
        if artifact is None or artifact.user_id != user_id or artifact.updated_at > stale_before:
            return None
        recovered = replace(artifact, updated_at=datetime.now(UTC))
        self.artifacts[artifact_id] = recovered
        return recovered

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


class MemoryFlatLays:
    def __init__(self, view: ItemPresentationView | None) -> None:
        self.view = view

    async def get_current_flat_lay_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
    ) -> ItemPresentationView | None:
        if self.view is None:
            return None
        if self.view.user_id != user_id or self.view.item_id != item_id:
            return None
        return self.view


class RecordingCollageRenderer:
    def __init__(self) -> None:
        self.images: tuple[ImagePayload, ...] = ()

    def render(self, images: Sequence[ImagePayload]) -> ImagePayload:
        self.images = tuple(images)
        return payload("derived/renders/recorded.png", (250, 250, 250))


class SuccessfulPixelGenerator:
    def __init__(self) -> None:
        self.images: tuple[ImagePayload, ...] = ()
        self.prompt = ""
        self.size = ""
        self.seed: int | None = None
        self.guidance_scale: float | None = None

    async def generate(
        self,
        *,
        prompt: str,
        images: tuple[ImagePayload, ...],
        size: str = "1024x1024",
        seed: int | None = None,
        guidance_scale: float | None = None,
    ) -> GeneratedImage:
        self.prompt = prompt
        self.images = images
        self.size = size
        self.seed = seed
        self.guidance_scale = guidance_scale
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


class RecordingSpriteExtractor:
    def __init__(self) -> None:
        self.source: ImagePayload | None = None

    def extract(self, image: ImagePayload) -> ImagePayload:
        self.source = image
        return payload("derived/render-sprites/pixel.png", (10, 20, 30))


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


class SuccessfulAuditedTryOnGenerator:
    def __init__(self) -> None:
        self.model_image: ImagePayload | None = None
        self.outfit_board: ImagePayload | None = None

    async def try_on(
        self,
        *,
        model_image: ImagePayload,
        outfit_board: ImagePayload,
    ) -> GeneratedImage:
        self.model_image = model_image
        self.outfit_board = outfit_board
        body = png((80, 120, 200))
        return GeneratedImage(
            body=body,
            content_type="image/jpeg",
            sha256=sha256(body).hexdigest(),
            provider_trace=RenderProviderTrace(
                provider="doubao_virtual_try_on_skill",
                model="audited_identity_locked_workflow",
                parameters={"skill_version": "1.4.3", "hard_pass": True},
            ),
        )


class FailingAuditedTryOnGenerator:
    def __init__(
        self,
        *,
        code: str = "try_on_identity_audit_failed",
        message: str = "candidate did not preserve identity",
    ) -> None:
        self.calls = 0
        self.code = code
        self.message = message

    async def try_on(
        self,
        *,
        model_image: ImagePayload,
        outfit_board: ImagePayload,
    ) -> GeneratedImage:
        self.calls += 1
        raise RenderProviderError(
            self.code,
            self.message,
            retryable=False,
        )


class InvalidResultAuditedTryOnGenerator:
    async def try_on(
        self,
        *,
        model_image: ImagePayload,
        outfit_board: ImagePayload,
    ) -> GeneratedImage:
        raise ValueError("generated result is malformed")


class CorruptPixelGenerator:
    async def generate(
        self,
        *,
        prompt: str,
        images: tuple[ImagePayload, ...],
        size: str = "1024x1024",
        seed: int | None = None,
        guidance_scale: float | None = None,
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


def flat_lay_view(
    *,
    user_id: UUID,
    item_id: UUID,
    object_key: str | None,
    status: ItemPresentationStatus,
) -> ItemPresentationView:
    now = datetime.now(UTC)
    return ItemPresentationView(
        id=uuid4(),
        user_id=user_id,
        item_id=item_id,
        kind=ItemPresentationKind.FLAT_LAY_ITEM,
        status=status,
        object_key=object_key,
        content_hash="f" * 64 if object_key is not None else None,
        content_type="image/png" if object_key is not None else None,
        failure_code=None,
        failure_message=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_collage_prefers_the_generated_item_flat_lay_over_the_capture_crop() -> None:
    user_id, detail, item, objects = fixture()
    generated_flat_lay = payload("derived/items/flat-lay/top.png", (255, 255, 255))
    objects.images[generated_flat_lay.object_key] = generated_flat_lay
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="flat-lay-collage",
    )
    repository = MemoryRenderRepository([collage])
    renderer = RecordingCollageRenderer()
    processor = RenderProcessor(
        artifacts=repository,
        renders=RenderApplication(artifacts=repository),
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=renderer,
        pixel_generator=None,
        try_on_generator=None,
        fixed_model_object_key=None,
        item_presentations=MemoryFlatLays(
            flat_lay_view(
                user_id=user_id,
                item_id=item.id,
                object_key=generated_flat_lay.object_key,
                status=ItemPresentationStatus.SUCCEEDED,
            )
        ),
    )

    await processor.process(user_id=user_id, artifact_id=collage.id)

    assert renderer.images[0].object_key == generated_flat_lay.object_key
    assert renderer.images[0].object_key != item.display_object_key


@pytest.mark.asyncio
async def test_collage_waits_while_the_generated_item_flat_lay_is_running() -> None:
    user_id, detail, item, objects = fixture()
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="wait-for-flat-lay",
    )
    repository = MemoryRenderRepository([collage])
    processor = RenderProcessor(
        artifacts=repository,
        renders=RenderApplication(artifacts=repository),
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=RecordingCollageRenderer(),
        pixel_generator=None,
        try_on_generator=None,
        fixed_model_object_key=None,
        item_presentations=MemoryFlatLays(
            flat_lay_view(
                user_id=user_id,
                item_id=item.id,
                object_key=None,
                status=ItemPresentationStatus.RUNNING,
            )
        ),
    )

    with pytest.raises(RetryableRenderError, match="flat-lay is not ready"):
        await processor.process(user_id=user_id, artifact_id=collage.id)


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
    sprite_extractor = RecordingSpriteExtractor()
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
        pixel_sprite_extractor=sprite_extractor,
    )

    await processor.process(user_id=user_id, artifact_id=collage.id)
    await processor.process(user_id=user_id, artifact_id=pixel.id)

    stored_collage = repository.artifacts[collage.id]
    stored_pixel = repository.artifacts[pixel.id]
    assert stored_collage.status is RenderArtifactStatus.SUCCEEDED
    assert stored_collage.output is not None
    assert stored_pixel.status is RenderArtifactStatus.SUCCEEDED
    assert stored_pixel.output is not None
    assert stored_pixel.sprite_output is not None
    assert stored_pixel.sprite_output.object_key.startswith("derived/render-sprites/")
    assert stored_pixel.sprite_output.content_type == "image/png"
    assert sprite_extractor.source is not None
    assert stored_pixel.share_eligible is True
    assert stored_pixel.provider_trace is not None
    assert stored_pixel.provider_trace.provider == "test-private"
    assert stored_pixel.provider_trace.parameters["capability_id"] == "look.pixel_cover"
    assert stored_pixel.provider_trace.parameters["capability_alias"] == "image_generation"
    assert (
        stored_pixel.provider_trace.parameters["prompt_version"]
        == "look-pixel-cover-zh-v12-no-outfit-ornaments"
    )
    assert (
        stored_pixel.provider_trace.parameters["style_reference_version"]
        == "pixel-card-style-v2-candidate"
    )
    assert "第一张图是唯一内容图" in pixel_generator.prompt
    assert "最后两张图只提供画风" in pixel_generator.prompt
    assert "若第一张图是单品拼贴" in pixel_generator.prompt
    assert "不得把拼贴单品变成背景装饰" in pixel_generator.prompt
    assert "3:4" in pixel_generator.prompt
    assert "不画完整场景" in pixel_generator.prompt
    assert "眼睛较大圆润有高光" in pixel_generator.prompt
    assert "鼻子只用" not in pixel_generator.prompt
    assert "避免大面积纯白或中性灰" in pixel_generator.prompt
    assert "单个不超过人物头宽四分之一" in pixel_generator.prompt
    assert "仅当内容图有明确场景标志物时" in pixel_generator.prompt
    assert "否则只用星芒、圆点、菱形等简单符号" in pixel_generator.prompt
    assert "服装、鞋、包和首饰只属于人物" in pixel_generator.prompt
    assert "禁止复制为漂浮图标" in pixel_generator.prompt
    assert stored_pixel.provider_trace.parameters["schema_version"] == "generated-image-v1"
    assert len(pixel_generator.images) == 3
    assert pixel_generator.size == "1728x2304"
    assert pixel_generator.images[0].object_key == look_source.object_key
    assert stored_pixel.provider_trace.parameters["input_source_kind"] == "look_display"
    assert stored_pixel.provider_trace.parameters["content_image_count"] == 1
    assert pixel_generator.images[-2].object_key.endswith("anchor-formal-light-pixel.png")
    assert pixel_generator.images[-1].object_key.endswith("anchor-casual-dark-pixel.png")
    assert pixel_generator.seed is not None
    assert pixel_generator.guidance_scale is None


@pytest.mark.asyncio
async def test_pixel_cover_uses_collage_only_when_look_has_no_original_image() -> None:
    user_id, detail, item, objects = fixture()
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage-only-source",
    )
    pixel = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.PIXEL_COVER,
        request_key="pixel-from-collage-only",
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
        pixel_sprite_extractor=RecordingSpriteExtractor(),
    )

    await processor.process(user_id=user_id, artifact_id=collage.id)
    await processor.process(user_id=user_id, artifact_id=pixel.id)

    stored_collage = repository.artifacts[collage.id]
    stored_pixel = repository.artifacts[pixel.id]
    assert stored_collage.output is not None
    assert pixel_generator.images[0].object_key == stored_collage.output.object_key
    assert len(pixel_generator.images) == 3
    assert stored_pixel.provider_trace is not None
    assert stored_pixel.provider_trace.parameters["input_source_kind"] == "collage"
    assert stored_pixel.provider_trace.parameters["content_image_count"] == 1


@pytest.mark.asyncio
async def test_pixel_cover_uses_completed_try_on_as_its_only_content_source() -> None:
    user_id, detail, item, objects = fixture()
    try_on_image = payload("derived/renders/personal-try-on.png", (32, 96, 160))
    objects.images[try_on_image.object_key] = try_on_image
    try_on = (
        queued(
            user_id=user_id,
            look_id=detail.look.id,
            kind=RenderArtifactKind.TRY_ON,
            request_key="completed-personal-try-on",
        )
        .mark_running()
        .mark_succeeded(
            RenderOutput(
                object_key=try_on_image.object_key,
                content_hash=try_on_image.sha256,
                content_type=try_on_image.content_type,
            )
        )
    )
    pixel = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.PIXEL_COVER,
        request_key="pixel-from-personal-try-on",
        source_artifact_id=try_on.id,
    )
    repository = MemoryRenderRepository([try_on, pixel])
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
        pixel_sprite_extractor=RecordingSpriteExtractor(),
    )

    await processor.process(user_id=user_id, artifact_id=pixel.id)

    stored = repository.artifacts[pixel.id]
    assert stored.status is RenderArtifactStatus.SUCCEEDED
    assert pixel_generator.images[0].object_key == try_on_image.object_key
    assert len(pixel_generator.images) == 3
    assert stored.provider_trace is not None
    assert stored.provider_trace.parameters["input_source_kind"] == "try_on"
    assert stored.provider_trace.parameters["content_image_count"] == 1


@pytest.mark.asyncio
async def test_processor_backfills_a_sprite_for_an_existing_pixel_card() -> None:
    user_id, detail, item, objects = fixture()
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="backfill-collage",
    )
    pixel = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.PIXEL_COVER,
        request_key="backfill-pixel",
        source_artifact_id=collage.id,
    )
    repository = MemoryRenderRepository([collage, pixel])
    base_arguments = {
        "artifacts": repository,
        "renders": RenderApplication(artifacts=repository),
        "looks": MemoryLookRepository(detail),
        "wardrobe": MemoryWardrobeRepository(item),
        "objects": objects,
        "collages": PillowLookCollageRenderer(canvas_size=320),
        "try_on_generator": None,
        "fixed_model_object_key": None,
    }
    first_processor = RenderProcessor(
        **base_arguments,  # type: ignore[arg-type]
        pixel_generator=SuccessfulPixelGenerator(),
    )

    await first_processor.process(user_id=user_id, artifact_id=collage.id)
    await first_processor.process(user_id=user_id, artifact_id=pixel.id)
    assert repository.artifacts[pixel.id].sprite_output is None

    extractor = RecordingSpriteExtractor()
    backfill_processor = RenderProcessor(
        **base_arguments,  # type: ignore[arg-type]
        pixel_generator=None,
        pixel_sprite_extractor=extractor,
    )
    await backfill_processor.process(user_id=user_id, artifact_id=pixel.id)

    stored = repository.artifacts[pixel.id]
    assert stored.status is RenderArtifactStatus.SUCCEEDED
    assert stored.sprite_output is not None
    assert stored.sprite_output.object_key.startswith("derived/render-sprites/")
    assert extractor.source is not None


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
    assert stored.provider_trace.parameters["prompt_version"] == "look-virtual-try-on-zh-v3"
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
    assert stored.provider_trace.parameters["prompt_version"] == "look-virtual-try-on-zh-v3"
    assert stored.provider_trace.parameters["image_count"] == 2
    assert stored.provider_trace.parameters["size"] == "1728x2304"
    assert dedicated_try_on.categories == []


@pytest.mark.asyncio
async def test_personal_try_on_prefers_audited_doubao_skill_workflow() -> None:
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
    audited = SuccessfulAuditedTryOnGenerator()
    legacy_image_generator = SuccessfulPixelGenerator()
    dedicated_try_on = SuccessfulTryOnGenerator()
    processor = RenderProcessor(
        artifacts=repository,
        renders=renders,
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=legacy_image_generator,
        try_on_generator=dedicated_try_on,
        audited_try_on_generator=audited,
        fixed_model_object_key=None,
    )
    await processor.process(user_id=user_id, artifact_id=collage.id)
    artifact = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.TRY_ON,
        request_key="personal-audited-skill",
        source_artifact_id=collage.id,
        subject_object_key=subject.object_key,
    )
    repository.artifacts[artifact.id] = artifact

    await processor.process(user_id=user_id, artifact_id=artifact.id)

    stored = repository.artifacts[artifact.id]
    assert stored.status is RenderArtifactStatus.SUCCEEDED
    assert audited.model_image is not None
    assert audited.model_image.sha256 == subject.sha256
    assert audited.outfit_board is not None
    assert dedicated_try_on.categories == []
    assert stored.provider_trace is not None
    assert stored.provider_trace.parameters["capability_alias"] == ("doubao_virtual_try_on_skill")
    assert stored.provider_trace.parameters["strategy"] == ("analyze_generate_audit_retry")
    assert stored.provider_trace.parameters["prompt_version"] == (
        "doubao-virtual-try-on-skill-v1.4.3"
    )


@pytest.mark.parametrize(
    ("code", "expected_message"),
    [
        (
            "try_on_identity_audit_failed",
            "本次试穿图未达到可用质量，请重新尝试。",  # noqa: RUF001
        ),
        (
            "render_provider_unavailable",
            "真人试穿服务暂时不可用，请稍后重试。",  # noqa: RUF001
        ),
        (
            "render_provider_schema_invalid",
            "本次试穿图生成失败，请重新尝试。",  # noqa: RUF001
        ),
    ],
)
@pytest.mark.asyncio
async def test_failed_audited_try_on_uses_specific_user_facing_message(
    code: str,
    expected_message: str,
) -> None:
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
    audited = FailingAuditedTryOnGenerator(code=code)
    legacy_image_generator = SuccessfulPixelGenerator()
    dedicated_try_on = SuccessfulTryOnGenerator()
    processor = RenderProcessor(
        artifacts=repository,
        renders=renders,
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=legacy_image_generator,
        try_on_generator=dedicated_try_on,
        audited_try_on_generator=audited,
        fixed_model_object_key=None,
    )
    await processor.process(user_id=user_id, artifact_id=collage.id)
    artifact = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.TRY_ON,
        request_key="personal-failed-audited-skill",
        source_artifact_id=collage.id,
        subject_object_key=subject.object_key,
    )
    repository.artifacts[artifact.id] = artifact

    await processor.process(user_id=user_id, artifact_id=artifact.id)

    stored = repository.artifacts[artifact.id]
    assert stored.status is RenderArtifactStatus.DEGRADED
    assert stored.failure_message == expected_message
    assert audited.calls == 1
    assert legacy_image_generator.images == ()
    assert dedicated_try_on.categories == []


@pytest.mark.asyncio
async def test_source_photo_rejection_reason_is_persisted_for_h5() -> None:
    user_id, detail, item, objects = fixture()
    subject = payload("originals/upload/cropped.png", (160, 130, 110))
    objects.images[subject.object_key] = subject
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage-source-rejection",
    )
    repository = MemoryRenderRepository([collage])
    renders = RenderApplication(artifacts=repository)
    reason = "照片只到大腿，请重新上传至少露出膝盖和小腿的照片。"  # noqa: RUF001
    audited = FailingAuditedTryOnGenerator(
        code="try_on_source_photo_ineligible",
        message=reason,
    )
    processor = RenderProcessor(
        artifacts=repository,
        renders=renders,
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=None,
        try_on_generator=None,
        audited_try_on_generator=audited,
        fixed_model_object_key=None,
    )
    await processor.process(user_id=user_id, artifact_id=collage.id)
    artifact = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.TRY_ON,
        request_key="personal-source-rejection",
        source_artifact_id=collage.id,
        subject_object_key=subject.object_key,
    )
    repository.artifacts[artifact.id] = artifact

    await processor.process(user_id=user_id, artifact_id=artifact.id)

    stored = repository.artifacts[artifact.id]
    assert stored.status is RenderArtifactStatus.DEGRADED
    assert stored.failure_message == reason


@pytest.mark.asyncio
async def test_invalid_audited_try_on_result_uses_generation_failure_message() -> None:
    user_id, detail, item, objects = fixture()
    subject = payload("originals/upload/my-full-body.png", (160, 130, 110))
    objects.images[subject.object_key] = subject
    collage = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.COLLAGE,
        request_key="collage-invalid-audited-result",
    )
    repository = MemoryRenderRepository([collage])
    processor = RenderProcessor(
        artifacts=repository,
        renders=RenderApplication(artifacts=repository),
        looks=MemoryLookRepository(detail),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobeRepository(item),
        objects=objects,
        collages=PillowLookCollageRenderer(canvas_size=320),
        pixel_generator=None,
        try_on_generator=None,
        audited_try_on_generator=InvalidResultAuditedTryOnGenerator(),
        fixed_model_object_key=None,
    )
    await processor.process(user_id=user_id, artifact_id=collage.id)
    artifact = queued(
        user_id=user_id,
        look_id=detail.look.id,
        kind=RenderArtifactKind.TRY_ON,
        request_key="personal-invalid-audited-result",
        source_artifact_id=collage.id,
        subject_object_key=subject.object_key,
    )
    repository.artifacts[artifact.id] = artifact

    await processor.process(user_id=user_id, artifact_id=artifact.id)

    stored = repository.artifacts[artifact.id]
    assert stored.status is RenderArtifactStatus.DEGRADED
    assert stored.failure_message == "本次试穿图生成失败，请重新尝试。"  # noqa: RUF001


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
