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
    def __init__(self, source: ImagePayload) -> None:
        self.images = {source.object_key: source}

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
