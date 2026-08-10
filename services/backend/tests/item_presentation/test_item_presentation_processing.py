from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from typing import cast
from uuid import UUID, uuid4

import pytest
from PIL import Image, ImageDraw, ImageFilter
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
    normalize_flat_lay_image,
    normalize_flat_lay_output,
    normalize_pixel_card_output,
)
from stylecapture_backend.features.render.domain import RenderInputSignature, RenderProviderTrace
from stylecapture_backend.features.render.infrastructure.collage import PillowLookCollageRenderer
from stylecapture_backend.features.render.ports import GeneratedImage, RenderProviderError
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
        assert "不要生成圆形或椭圆形光晕" in prompt
        assert "落地阴影、投影、边框" in prompt
        assert len(images) == 1
        self.images = tuple(images)
        rendered = Image.new("RGB", (2048, 2048), (238, 238, 238))
        rendered.paste((223, 157, 38), (500, 480, 1548, 1580))
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
        assert "数字纯白 #FFFFFF" in prompt
        assert "灰白、米白、纸张纹理、污点、斑块、渐变" in prompt
        assert "禁止接触阴影和投影" in prompt
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


def test_ai_flat_lay_whitens_gray_blotches_without_erasing_light_item() -> None:
    rendered = Image.new("RGB", (1728, 2304), "white")
    rendered.paste((236, 236, 236), (150, 420, 360, 720))
    rendered.paste((228, 228, 228), (1360, 1480, 1560, 1760))
    rendered.paste((180, 176, 170), (590, 520, 1138, 1784))
    rendered.paste((232, 230, 226), (620, 550, 1108, 1754))
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    body = buffer.getvalue()
    generated = GeneratedImage(
        body=body,
        content_type="image/png",
        sha256=sha256(body).hexdigest(),
        provider_trace=RenderProviderTrace(
            provider="litellm",
            model="image_generation",
            parameters={},
        ),
    )

    normalized, quality = normalize_flat_lay_output(generated)

    assert quality["quality_gate"] == "pure-white-3x4-v2"
    assert quality["background_cleanup"] == "silhouette-protected-pure-white-v2"
    with Image.open(BytesIO(normalized.body)) as image:
        assert image.getpixel((200, 500)) == (255, 255, 255)
        assert image.getpixel((1450, 1600)) == (255, 255, 255)
        assert image.getpixel((800, 900)) == (232, 230, 226)


def test_ai_flat_lay_preserves_a_thin_pale_necklace() -> None:
    rendered = Image.new("RGB", (1728, 2304), "white")
    draw = ImageDraw.Draw(rendered)
    necklace = (218, 214, 204)
    draw.line(((620, 520), (864, 1420), (1108, 520)), fill=necklace, width=12)
    draw.ellipse((815, 1370, 913, 1468), fill=(58, 42, 35))
    draw.rectangle((120, 900, 320, 1180), fill=(234, 234, 234))
    assert rendered.getpixel((742, 970)) == necklace
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    body = buffer.getvalue()
    generated = GeneratedImage(
        body=body,
        content_type="image/png",
        sha256=sha256(body).hexdigest(),
        provider_trace=RenderProviderTrace(
            provider="litellm",
            model="image_generation",
            parameters={},
        ),
    )

    normalized, quality = normalize_flat_lay_output(generated)

    with Image.open(BytesIO(normalized.body)) as image:
        assert image.getpixel((742, 970)) == necklace, quality
        assert image.getpixel((200, 1000)) == (255, 255, 255)


def test_ai_flat_lay_does_not_bleach_a_nearly_white_garment() -> None:
    rendered = Image.new("RGB", (1728, 2304), "white")
    draw = ImageDraw.Draw(rendered)
    garment = (250, 250, 248)
    draw.rounded_rectangle(
        (470, 440, 1258, 1840),
        radius=120,
        fill=garment,
        outline=(218, 216, 210),
        width=10,
    )
    for y in range(650, 1650, 180):
        draw.ellipse((850, y, 866, y + 16), fill=(155, 112, 82))
    draw.rectangle((90, 820, 300, 1120), fill=(235, 235, 235))
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    body = buffer.getvalue()
    generated = GeneratedImage(
        body=body,
        content_type="image/png",
        sha256=sha256(body).hexdigest(),
        provider_trace=RenderProviderTrace(
            provider="litellm",
            model="image_generation",
            parameters={},
        ),
    )

    normalized, _ = normalize_flat_lay_output(generated)

    with Image.open(BytesIO(normalized.body)) as image:
        assert image.getpixel((700, 900)) == garment
        assert image.getpixel((858, 650)) == (155, 112, 82)
        assert image.getpixel((180, 950)) == (255, 255, 255)


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
    assert stored.provider_trace.parameters["prompt_version"] == (
        "stylecapture-item-pixel-2026-08-09-clean-subject"
    )
    assert stored.provider_trace.parameters["schema_version"] == (
        "ornate-asymmetric-pixel-card-square-v4"
    )
    assert stored.provider_trace.parameters["output_canvas"] == "1024x1024"
    assert stored.provider_trace.parameters["background_palette"] in {
        "蜜桃",
        "丁香紫",
        "晴空蓝",
        "薄荷绿",
        "奶油黄",
        "莓果粉",
    }


def test_pixel_card_recolors_connected_gray_background_with_stable_variety() -> None:
    rendered = Image.new("RGB", (2048, 2048), (238, 238, 238))
    rendered.paste((190, 40, 55), (620, 440, 1428, 1640))
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    body = buffer.getvalue()
    generated = GeneratedImage(
        body=body,
        content_type="image/png",
        sha256=sha256(body).hexdigest(),
        provider_trace=RenderProviderTrace(
            provider="litellm", model="image_generation", parameters={}
        ),
    )

    first, first_quality = normalize_pixel_card_output(generated, seed="item-a")
    second, second_quality = normalize_pixel_card_output(generated, seed="item-c")

    assert first_quality["background_palette"] != second_quality["background_palette"]
    recolored_ratio = first_quality["background_recolored_ratio"]
    assert isinstance(recolored_ratio, float)
    assert recolored_ratio > 0.5
    assert first_quality["decorations"] == "stylecapture-ornate-asymmetric-frame-v4"
    assert first_quality["decoration_count"] == 6
    with Image.open(BytesIO(first.body)) as first_card:
        assert first_card.size == (1024, 1024)
        corner_frame = cast(tuple[int, int, int], first_card.getpixel((76, 20)))
        assert max(corner_frame) - min(corner_frame) >= 8
        subject = cast(tuple[int, int, int], first_card.getpixel((512, 512)))
        assert subject[0] > 150 and subject[1] < 90
        center_backdrop = cast(tuple[int, int, int], first_card.getpixel((512, 160)))
        assert min(center_backdrop) > 220
        left_sparkle = cast(tuple[int, int, int], first_card.getpixel((188, 136)))
        mirrored_position = cast(tuple[int, int, int], first_card.getpixel((836, 136)))
        assert left_sparkle != mirrored_position
        first_outer = cast(tuple[int, int, int], first_card.getpixel((12, 12)))
    with Image.open(BytesIO(second.body)) as second_card:
        assert second_card.getpixel((12, 12)) != first_outer


def test_pixel_card_softens_perimeter_black_outline_on_light_items() -> None:
    rendered = Image.new("RGB", (2048, 2048), (238, 238, 238))
    draw = ImageDraw.Draw(rendered)
    draw.rectangle((620, 520, 660, 1528), fill=(20, 18, 16))
    draw.rectangle((660, 520, 1428, 1528), fill=(226, 196, 124))
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    body = buffer.getvalue()
    generated = GeneratedImage(
        body=body,
        content_type="image/png",
        sha256=sha256(body).hexdigest(),
        provider_trace=RenderProviderTrace(
            provider="litellm", model="image_generation", parameters={}
        ),
    )

    normalized, quality = normalize_pixel_card_output(generated, seed="light-shirt")

    assert quality["outline_color"] == "#684E38"
    assert cast(float, quality["softened_outline_ratio"]) > 0
    with Image.open(BytesIO(normalized.body)) as card:
        assert card.getpixel((320, 512)) == (104, 78, 56)


def test_pixel_card_keeps_dark_item_edges_dark() -> None:
    rendered = Image.new("RGB", (2048, 2048), (238, 238, 238))
    draw = ImageDraw.Draw(rendered)
    draw.rectangle((620, 520, 1428, 1528), fill=(22, 22, 24))
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    body = buffer.getvalue()
    generated = GeneratedImage(
        body=body,
        content_type="image/png",
        sha256=sha256(body).hexdigest(),
        provider_trace=RenderProviderTrace(
            provider="litellm", model="image_generation", parameters={}
        ),
    )

    normalized, quality = normalize_pixel_card_output(generated, seed="black-shoes")

    assert quality["softened_outline_ratio"] == 0
    with Image.open(BytesIO(normalized.body)) as card:
        edge = cast(tuple[int, int, int], card.getpixel((316, 512)))
        assert max(edge) <= 40


def test_pixel_card_rejects_non_square_provider_output() -> None:
    rendered = Image.new("RGB", (1728, 2304), "white")
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    body = buffer.getvalue()
    generated = GeneratedImage(
        body=body,
        content_type="image/png",
        sha256=sha256(body).hexdigest(),
        provider_trace=RenderProviderTrace(
            provider="litellm", model="image_generation", parameters={}
        ),
    )

    with pytest.raises(RenderProviderError, match="square"):
        normalize_pixel_card_output(generated)


def test_pixel_card_rejects_thin_dark_halo_around_light_item() -> None:
    rendered = Image.new("RGB", (2048, 2048), (248, 248, 248))
    draw = ImageDraw.Draw(rendered)
    draw.rectangle((590, 410, 1458, 1668), fill=(28, 24, 24))
    draw.rectangle((640, 460, 1408, 1618), fill=(232, 154, 74))
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    body = buffer.getvalue()
    generated = GeneratedImage(
        body=body,
        content_type="image/png",
        sha256=sha256(body).hexdigest(),
        provider_trace=RenderProviderTrace(
            provider="litellm", model="image_generation", parameters={}
        ),
    )

    with pytest.raises(RenderProviderError, match="halo"):
        normalize_pixel_card_output(generated)


def test_pixel_card_cleans_broad_gray_background_haze() -> None:
    rendered = Image.new("RGB", (2048, 2048), (248, 248, 248))
    haze = Image.new("RGBA", rendered.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(haze)
    draw.ellipse((360, 250, 1688, 1788), fill=(30, 26, 28, 138))
    haze = haze.filter(ImageFilter.GaussianBlur(radius=180))
    rendered = Image.alpha_composite(rendered.convert("RGBA"), haze).convert("RGB")
    draw = ImageDraw.Draw(rendered)
    draw.rectangle((650, 520, 1398, 1608), fill=(232, 154, 74))
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    body = buffer.getvalue()
    generated = GeneratedImage(
        body=body,
        content_type="image/png",
        sha256=sha256(body).hexdigest(),
        provider_trace=RenderProviderTrace(
            provider="litellm", model="image_generation", parameters={}
        ),
    )

    normalized, quality = normalize_pixel_card_output(generated)

    assert cast(float, quality["background_recolored_ratio"]) > 0.55
    with Image.open(BytesIO(normalized.body)) as card:
        left_haze_area = cast(tuple[int, int, int], card.getpixel((230, 512)))
        assert min(left_haze_area) > 210


def test_flat_lay_rejects_thin_dark_halo_on_white_background() -> None:
    rendered = Image.new("RGB", (1728, 2304), (255, 255, 255))
    draw = ImageDraw.Draw(rendered)
    draw.rectangle((470, 530, 1258, 1774), fill=(22, 20, 20))
    draw.rectangle((520, 580, 1208, 1724), fill=(86, 162, 205))
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")

    with pytest.raises(RenderProviderError, match="halo"):
        normalize_flat_lay_image(buffer.getvalue())


def test_flat_lay_cleans_broad_gray_background_haze() -> None:
    rendered = Image.new("RGB", (1728, 2304), (255, 255, 255))
    haze = Image.new("RGBA", rendered.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(haze)
    draw.ellipse((250, 300, 1478, 1950), fill=(30, 26, 28, 126))
    haze = haze.filter(ImageFilter.GaussianBlur(radius=150))
    rendered = Image.alpha_composite(rendered.convert("RGBA"), haze).convert("RGB")
    draw = ImageDraw.Draw(rendered)
    draw.rectangle((520, 580, 1208, 1724), fill=(86, 162, 205))
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")

    normalized, quality = normalize_flat_lay_image(buffer.getvalue())

    assert cast(float, quality["background_cleaned_ratio"]) > 0.5
    with Image.open(BytesIO(normalized.body)) as flat_lay:
        assert flat_lay.getpixel((360, 1152)) == (255, 255, 255)


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
    assert stored.input_signature.version == "item-flat-lay-v3"
    assert generator.images[0].object_key == source.object_key
    assert generator.size == "1728x2304"
    assert stored.provider_trace is not None
    assert stored.provider_trace.parameters["schema_version"] == ("seedream-pure-white-3x4-v2")
    assert stored.provider_trace.parameters["quality_gate"] == "pure-white-3x4-v2"
    assert stored.provider_trace.parameters["background_cleanup"] == (
        "silhouette-protected-pure-white-v2"
    )
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
