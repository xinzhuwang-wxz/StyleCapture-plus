from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from PIL import Image
from pillow_heif import from_pillow
from stylecapture_backend.features.capture.domain import (
    CaptureSourceKind,
    ImagePayload,
    OwnershipState,
)
from stylecapture_backend.features.item_presentation.application import (
    ItemPresentationApplication,
    flat_lay_item_signature,
    pixel_item_signature,
)
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationAsset,
    ItemPresentationKind,
    ItemPresentationStatus,
)
from stylecapture_backend.features.item_presentation.processing import (
    ItemPresentationProcessor,
)
from stylecapture_backend.features.render.domain import RenderInputSignature, RenderProviderTrace
from stylecapture_backend.features.render.infrastructure.collage import PillowLookCollageRenderer
from stylecapture_backend.features.render.ports import GeneratedImage
from stylecapture_backend.features.wardrobe.domain import ItemAttributes, ItemStatus, WardrobeItem


class MemoryPresentations:
    def __init__(self, asset: ItemPresentationAsset) -> None:
        self.assets = {asset.id: asset}

    async def ensure_requested(self, asset: ItemPresentationAsset) -> ItemPresentationAsset:
        self.assets.setdefault(asset.id, asset)
        return self.assets[asset.id]

    async def save(self, asset: ItemPresentationAsset) -> ItemPresentationAsset:
        self.assets[asset.id] = asset
        return asset

    async def find_current(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        kind: ItemPresentationKind,
        input_signature: RenderInputSignature,
    ) -> ItemPresentationAsset | None:
        return None

    async def get_for_user(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
    ) -> ItemPresentationAsset | None:
        asset = self.assets.get(asset_id)
        return asset if asset is not None and asset.user_id == user_id else None


class OneItemWardrobe:
    def __init__(self, item: WardrobeItem) -> None:
        self.item = item

    async def get_item(self, user_id: UUID, item_id: UUID) -> WardrobeItem:
        assert (user_id, item_id) == (self.item.user_id, self.item.id)
        return self.item


class MemoryObjects:
    def __init__(self, *sources: ImagePayload) -> None:
        self.images = {source.object_key: source for source in sources}

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


class SuccessfulGenerator:
    def __init__(self) -> None:
        self.images: tuple[ImagePayload, ...] = ()

    async def generate(
        self,
        *,
        prompt: str,
        images: Sequence[ImagePayload],
        size: str = "1024x1024",
    ) -> GeneratedImage:
        assert "只出现一个目标单品" in prompt
        assert len(images) == 1
        self.images = tuple(images)
        body = b"real-provider-item-pixel-output"
        return GeneratedImage(
            body=body,
            content_type="image/png",
            sha256=sha256(body).hexdigest(),
            provider_trace=RenderProviderTrace(
                provider="litellm",
                model="image_generation",
                parameters={"size": size},
            ),
        )


class FlatLayGenerator:
    def __init__(self) -> None:
        self.images: tuple[ImagePayload, ...] = ()
        self.size: str | None = None

    async def generate(
        self,
        *,
        prompt: str,
        images: Sequence[ImagePayload],
        size: str = "1024x1024",
    ) -> GeneratedImage:
        assert "严格竖版 3:4" in prompt
        assert "不要把其他单品的肩带、腰带、系带" in prompt
        self.images = tuple(images)
        self.size = size
        rendered = Image.new("RGB", (1728, 2304), (253, 253, 253))
        rendered.paste((80, 160, 200), (420, 480, 1308, 1824))
        buffer = BytesIO()
        rendered.save(buffer, format="PNG")
        body = buffer.getvalue()
        return GeneratedImage(
            body=body,
            content_type="image/png",
            sha256=sha256(body).hexdigest(),
            provider_trace=RenderProviderTrace(
                provider="litellm",
                model="image_generation",
                parameters={"size": size},
            ),
        )


class FailIfCalledGenerator:
    async def generate(
        self,
        *,
        prompt: str,
        images: Sequence[ImagePayload],
        size: str = "1024x1024",
    ) -> GeneratedImage:
        raise AssertionError("refined alpha cutouts must not call the image provider")


@pytest.mark.asyncio
async def test_item_pixel_records_capability_prompt_and_schema_versions() -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    source_body = b"normalized-real-item-image"
    source = ImagePayload(
        object_key="derived/items/display/top.png",
        content_type="image/png",
        body=source_body,
        sha256=sha256(source_body).hexdigest(),
    )
    item = WardrobeItem(
        id=uuid4(),
        user_id=user_id,
        capture_id=uuid4(),
        selection_key="top",
        source_object_key="originals/upload/outfit.png",
        display_object_key=source.object_key,
        source_available=True,
        source_kind=CaptureSourceKind.UPLOAD,
        ownership=OwnershipState.OWNED,
        status=ItemStatus.READY,
        attributes=ItemAttributes(),
        model_metadata={},
        embedding=None,
        created_at=now,
        updated_at=now,
    )
    asset = ItemPresentationAsset.queued(
        user_id=user_id,
        item_id=item.id,
        kind=ItemPresentationKind.PIXEL_ITEM,
        input_signature=pixel_item_signature(item),
        request_key="item-pixel-processing",
    )
    repository = MemoryPresentations(asset)
    wardrobe = OneItemWardrobe(item)
    generator = SuccessfulGenerator()
    processor = ItemPresentationProcessor(
        presentations=ItemPresentationApplication(assets=repository, wardrobe=wardrobe),
        wardrobe=wardrobe,
        objects=MemoryObjects(source),
        generator=generator,
    )

    await processor.process(user_id=user_id, asset_id=asset.id)

    stored = repository.assets[asset.id]
    assert stored.status is ItemPresentationStatus.SUCCEEDED
    assert stored.provider_trace is not None
    assert stored.provider_trace.parameters["capability_id"] == "item.pixel_presentation"
    assert stored.provider_trace.parameters["capability_alias"] == "image_generation"
    assert (
        stored.provider_trace.parameters["prompt_version"] == "stylecapture-item-pixel-2026-07-26"
    )
    assert stored.provider_trace.parameters["schema_version"] == "generated-image-v1"


@pytest.mark.asyncio
async def test_item_pixel_converts_heic_source_before_render_provider() -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    source = _heic_payload("originals/upload/sweater.heic")
    item = WardrobeItem(
        id=uuid4(),
        user_id=user_id,
        capture_id=uuid4(),
        selection_key="whole_capture",
        source_object_key=source.object_key,
        display_object_key=None,
        source_available=True,
        source_kind=CaptureSourceKind.UPLOAD,
        ownership=OwnershipState.OWNED,
        status=ItemStatus.READY,
        attributes=ItemAttributes(),
        model_metadata={},
        embedding=None,
        created_at=now,
        updated_at=now,
    )
    asset = ItemPresentationAsset.queued(
        user_id=user_id,
        item_id=item.id,
        kind=ItemPresentationKind.PIXEL_ITEM,
        input_signature=pixel_item_signature(item),
        request_key="item-pixel-heic",
    )
    repository = MemoryPresentations(asset)
    wardrobe = OneItemWardrobe(item)
    generator = SuccessfulGenerator()
    processor = ItemPresentationProcessor(
        presentations=ItemPresentationApplication(assets=repository, wardrobe=wardrobe),
        wardrobe=wardrobe,
        objects=MemoryObjects(source),
        generator=generator,
    )

    await processor.process(user_id=user_id, asset_id=asset.id)

    assert repository.assets[asset.id].status is ItemPresentationStatus.SUCCEEDED
    assert generator.images[0].content_type == "image/jpeg"
    assert generator.images[0].object_key.endswith(".render-input.jpg")


@pytest.mark.asyncio
async def test_flat_lay_uses_original_source_when_display_is_not_a_refined_cutout() -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    source = _png_payload("originals/upload/outfit.png", (120, 90, 60, 255))
    display = _png_payload("derived/items/display/cardigan.png", (80, 160, 200, 255))
    item = WardrobeItem(
        id=uuid4(),
        user_id=user_id,
        capture_id=uuid4(),
        selection_key="cardigan",
        source_object_key=source.object_key,
        display_object_key=display.object_key,
        source_available=True,
        source_kind=CaptureSourceKind.UPLOAD,
        ownership=OwnershipState.OWNED,
        status=ItemStatus.READY,
        attributes=ItemAttributes(),
        model_metadata={"segmentation": {"representation": "coarse_polygon"}},
        embedding=None,
        created_at=now,
        updated_at=now,
    )
    asset = ItemPresentationAsset.queued(
        user_id=user_id,
        item_id=item.id,
        kind=ItemPresentationKind.FLAT_LAY_ITEM,
        input_signature=flat_lay_item_signature(item),
        request_key="item-flat-lay-processing",
    )
    repository = MemoryPresentations(asset)
    wardrobe = OneItemWardrobe(item)
    generator = FlatLayGenerator()
    objects = MemoryObjects(source, display)
    processor = ItemPresentationProcessor(
        presentations=ItemPresentationApplication(assets=repository, wardrobe=wardrobe),
        wardrobe=wardrobe,
        objects=objects,
        generator=generator,
        flat_lays=PillowLookCollageRenderer(
            canvas_width=1728,
            canvas_height=2304,
            padding=144,
        ),
    )

    await processor.process(user_id=user_id, asset_id=asset.id)

    stored = repository.assets[asset.id]
    assert stored.status is ItemPresentationStatus.SUCCEEDED
    assert generator.images[0].object_key == source.object_key
    assert generator.size == "1728x2304"
    assert stored.output is not None
    assert stored.output.object_key.startswith(f"derived/items/flat-lay/{user_id}/{item.id}/")
    output = objects.images[stored.output.object_key]
    with Image.open(BytesIO(output.body)) as rendered:
        assert rendered.size == (1728, 2304)
        assert rendered.getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.asyncio
async def test_flat_lay_uses_pillow_only_for_a_refined_transparent_cutout() -> None:
    user_id = uuid4()
    now = datetime.now(UTC)
    cutout_image = Image.new("RGBA", (240, 360), (0, 0, 0, 0))
    cutout_image.paste((80, 160, 200, 255), (40, 30, 200, 330))
    buffer = BytesIO()
    cutout_image.save(buffer, format="PNG")
    cutout_body = buffer.getvalue()
    cutout = ImagePayload(
        object_key="derived/items/display/cardigan.png",
        content_type="image/png",
        body=cutout_body,
        sha256=sha256(cutout_body).hexdigest(),
    )
    item = WardrobeItem(
        id=uuid4(),
        user_id=user_id,
        capture_id=uuid4(),
        selection_key="cardigan",
        source_object_key="originals/feed/deleted-outfit.png",
        display_object_key=cutout.object_key,
        source_available=False,
        source_kind=CaptureSourceKind.FEED,
        ownership=OwnershipState.INSPIRATION,
        status=ItemStatus.READY,
        attributes=ItemAttributes(),
        model_metadata={"segmentation": {"representation": "refined_mask"}},
        embedding=None,
        created_at=now,
        updated_at=now,
    )
    asset = ItemPresentationAsset.queued(
        user_id=user_id,
        item_id=item.id,
        kind=ItemPresentationKind.FLAT_LAY_ITEM,
        input_signature=flat_lay_item_signature(item),
        request_key="item-flat-lay-refined-mask",
    )
    repository = MemoryPresentations(asset)
    wardrobe = OneItemWardrobe(item)
    objects = MemoryObjects(cutout)
    processor = ItemPresentationProcessor(
        presentations=ItemPresentationApplication(assets=repository, wardrobe=wardrobe),
        wardrobe=wardrobe,
        objects=objects,
        generator=FailIfCalledGenerator(),
        flat_lays=PillowLookCollageRenderer(
            canvas_width=1728,
            canvas_height=2304,
            padding=144,
        ),
    )

    await processor.process(user_id=user_id, asset_id=asset.id)

    stored = repository.assets[asset.id]
    assert stored.status is ItemPresentationStatus.SUCCEEDED
    assert stored.provider_trace is not None
    assert stored.provider_trace.provider == "pillow"
    assert stored.provider_trace.parameters["source"] == "refined_mask"


def _png_payload(object_key: str, color: tuple[int, int, int, int]) -> ImagePayload:
    image = Image.new("RGBA", (80, 120), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    body = buffer.getvalue()
    return ImagePayload(
        object_key=object_key,
        content_type="image/png",
        body=body,
        sha256=sha256(body).hexdigest(),
    )


def _heic_payload(object_key: str) -> ImagePayload:
    image = Image.new("RGB", (8, 6), (210, 180, 140))
    heif = from_pillow(image)
    buffer = BytesIO()
    heif.save(buffer, format="HEIF")
    body = buffer.getvalue()
    return ImagePayload(
        object_key=object_key,
        content_type="image/heic",
        body=body,
        sha256=sha256(body).hexdigest(),
    )
