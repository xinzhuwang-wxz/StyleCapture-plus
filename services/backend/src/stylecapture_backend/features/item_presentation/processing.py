from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from statistics import median
from typing import Protocol, cast
from uuid import UUID

from PIL import Image, ImageChops, ImageDraw, ImageFilter, UnidentifiedImageError
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.item_presentation.application import (
    FLAT_LAY_ITEM_CAPABILITY_ID,
    FLAT_LAY_ITEM_SCHEMA_VERSION,
    PIXEL_ITEM_CAPABILITY_ID,
    PIXEL_ITEM_PROMPT_VERSION,
    PIXEL_ITEM_SCHEMA_VERSION,
    ItemPresentationApplication,
)
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationKind,
    ItemPresentationStatus,
)
from stylecapture_backend.features.item_presentation.ports import (
    ItemPresentationNotFound,
    WardrobeItemReader,
)
from stylecapture_backend.features.render.domain import RenderOutput, RenderProviderTrace
from stylecapture_backend.features.render.ports import (
    CollageRenderer,
    CollageRenderError,
    GeneratedImage,
    RenderProviderError,
)
from stylecapture_backend.features.wardrobe.domain import FieldEnvelope, WardrobeItem
from stylecapture_backend.platform.image_normalization import normalize_provider_image


class RetryableItemPresentationError(RuntimeError):
    """The item presentation can be retried safely by the worker."""


class ItemPresentationObjectStore(Protocol):
    def read_image(self, object_key: str) -> ImagePayload: ...

    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload: ...


class ItemPixelImageGenerator(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        images: Sequence[ImagePayload],
        size: str = "1024x1024",
    ) -> GeneratedImage: ...


@dataclass(frozen=True, slots=True)
class PixelCardPalette:
    name: str
    outer: str
    center: str
    frame: str
    accent: str


PIXEL_CARD_PALETTES = (
    PixelCardPalette("蜜桃", "#FFF8F4", "#FDE8E4", "#F5C9D7", "#EE9875"),
    PixelCardPalette("丁香紫", "#FCF9FF", "#F0E8FA", "#E0CEF3", "#A98AE8"),
    PixelCardPalette("晴空蓝", "#F8FCFF", "#E8F3FB", "#C9DFEF", "#70A9E3"),
    PixelCardPalette("薄荷绿", "#F7FCF9", "#E7F4EC", "#C9E4D5", "#68B58D"),
    PixelCardPalette("奶油黄", "#FFFCF2", "#F9F0D7", "#EEDCA6", "#D4A23D"),
    PixelCardPalette("莓果粉", "#FFF8FB", "#FBE7EE", "#F3C7D7", "#E786AA"),
)


PIXEL_CARD_OUTLINE_COLOR = (104, 78, 56)


def pixel_card_palette(seed: UUID | str) -> PixelCardPalette:
    stable_hash = 0
    for character in str(seed):
        stable_hash = (stable_hash * 31 + ord(character)) & 0xFFFFFFFF
    return PIXEL_CARD_PALETTES[stable_hash % len(PIXEL_CARD_PALETTES)]


def pixel_item_prompt(item: WardrobeItem) -> str:
    fields = item.attributes.fields
    name = _field_text(fields, "description", "这件单品")
    category = _field_text(fields, "category", "服装")
    subcategory = _field_text(fields, "subcategory", "")
    colors = _field_text(fields, "colors", "")
    return f"""
只识别并提取参考图中的目标单品“{name}”(类别 {category}/{subcategory}, 主色 {colors}),
把它转换为 StyleCapture 统一的复古像素单品画。严格输出 1:1 正方形图片。

主体规则: 只出现一个目标单品; 鞋只保留一双配对鞋; 目标明确为一组配饰时才保留整组。
单品正面居中、完整可见、不裁切、不拉伸, 占画面约 60% 至 72%, 四周留出装饰安全区。
忠实保留原单品的主色、轮廓、图案、领口、袖型、褶皱、吊带和结构, 不新增看不见的部件。

像素风规则: 使用清晰硬边的 16-bit / 32-bit 商品像素画, 轮廓由深一档同色像素描边,
外轮廓禁止使用突兀纯黑描边; 用低饱和深棕或比主体深一档的柔和同色像素收边。
内部用有限色阶表达材质和褶皱; 像素块大小一致, 禁止局部写实、局部像素的混合风格,
禁止模糊、抗锯齿、油画、3D 渲染、照片质感、矢量插画或平滑渐变。

背景必须纯净、均匀、接近纯白, 与主体边缘清楚分离。不要生成圆形或椭圆形光晕、黑灰色光圈、
落地阴影、投影、边框、爱心、星星或文字; 卡面背景与装饰由后端统一绘制。禁止人物、人体、皮肤、头发、
模特、衣架、场景、其他衣物、品牌、水印、标签、价格、文字、拼贴、分镜、多个候选和额外道具。
""".strip()


def flat_lay_item_prompt(item: WardrobeItem) -> str:
    fields = item.attributes.fields
    name = _field_text(fields, "description", "这件单品")
    category = _field_text(fields, "category", "服装")
    subcategory = _field_text(fields, "subcategory", "")
    colors = _field_text(fields, "colors", "")
    materials = _field_text(fields, "materials", "")
    pattern = _field_text(fields, "pattern", "")
    silhouette = _field_text(fields, "silhouette", "")
    details = _field_text(fields, "details", "")
    shoe_rule = (
        "如果目标是鞋, 只展示原图中的一双配对鞋。"
        if "鞋" in f"{category}{subcategory}{name}"
        else "只展示这一件目标单品。"
    )
    separation_rule = (
        "先判断重叠区域分别属于哪件衣物。不要把其他单品的肩带、腰带、系带、纽扣、"
        "腰头或装饰复制到目标单品上。被遮挡处只做保守的同材质连续补全, 禁止新增装饰。"
    )
    return f"""
从这张真实人物穿搭截图或上传图片中, 只提取并重建目标单品“{name}”。
识别信息: 类别 {category}/{subcategory}; 主色 {colors}; 材质 {materials};
图案 {pattern}; 版型 {silhouette}; 关键细节 {details}。{shoe_rule}{separation_rule}

生成独立电商商品白底图: 严格竖版 3:4, 输出 1728x2304; 背景必须是平坦、均匀的数字纯白 #FFFFFF;
除目标单品外每一个背景像素都必须是 #FFFFFF。禁止灰白、米白、纸张纹理、污点、斑块、渐变、暗角和环境色;
目标单品居中、完整轮廓全部可见、四周保留充足白边, 不裁切、不拉伸、不压扁。
使用正面或最利于识别的轻微俯视角度, 写实高分辨率产品摄影, 忠实保留原图中
实际可见的颜色、版型、材质、褶裥、纽扣、吊带、孔洞和结构。

不要出现其他衣物、整套穿搭、人物、人体部位、皮肤、头发、眼镜、手机、背景、
游客、衣架、模特、文字、品牌、水印、边框或道具。不要臆造看不见的花纹和结构。
让单品自然悬浮在纯白画布上, 禁止接触阴影和投影; 禁止灰色矩形底、大面积阴影、插画、剪纸、
贴纸、像素画和杂志拼贴。
""".strip()


def _field_text(
    fields: Mapping[str, FieldEnvelope],
    key: str,
    default: str,
) -> str:
    field = fields.get(key)
    if field is None:
        return default
    value = field.value
    if isinstance(value, list):
        return "、".join(str(entry) for entry in value)
    return str(value)


class ItemPresentationProcessor:
    def __init__(
        self,
        *,
        presentations: ItemPresentationApplication,
        wardrobe: WardrobeItemReader,
        objects: ItemPresentationObjectStore,
        generator: ItemPixelImageGenerator,
        flat_lays: CollageRenderer | None = None,
    ) -> None:
        self._presentations = presentations
        self._wardrobe = wardrobe
        self._objects = objects
        self._generator = generator
        self._flat_lays = flat_lays

    async def process(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        final_attempt: bool = False,
    ) -> None:
        try:
            asset = await self._presentations.get(user_id=user_id, asset_id=asset_id)
        except ItemPresentationNotFound:
            return
        if asset.status in {ItemPresentationStatus.SUCCEEDED, ItemPresentationStatus.FAILED}:
            return
        if asset.kind not in {
            ItemPresentationKind.PIXEL_ITEM,
            ItemPresentationKind.FLAT_LAY_ITEM,
        }:
            await self._presentations.mark_failed(
                user_id=user_id,
                asset_id=asset_id,
                code="kind_unsupported",
                message="该展示类型暂时不支持生成",
            )
            return
        await self._presentations.mark_running(user_id=user_id, asset_id=asset_id)
        try:
            item = await self._wardrobe.get_item(user_id, asset.item_id)
            if asset.kind is ItemPresentationKind.FLAT_LAY_ITEM:
                pillow_result = self._render_refined_cutout(item)
                if pillow_result is not None:
                    rendered, quality = pillow_result
                    stored = self._objects.write_derived_image(
                        rendered,
                        owner_id=user_id,
                        prefix=f"derived/items/flat-lay/{user_id}/{asset.item_id}",
                    )
                    await self._presentations.mark_succeeded(
                        user_id=user_id,
                        asset_id=asset_id,
                        output=RenderOutput(
                            object_key=stored.object_key,
                            content_hash=stored.sha256,
                            content_type=stored.content_type,
                        ),
                        provider_trace=RenderProviderTrace(
                            provider="pillow",
                            model="refined-mask-flat-lay-v2",
                            parameters={
                                "capability_id": FLAT_LAY_ITEM_CAPABILITY_ID,
                                "schema_version": FLAT_LAY_ITEM_SCHEMA_VERSION,
                                "canvas": "1728x2304",
                                "background": "#FFFFFF",
                                "source": "refined_mask",
                                **quality,
                            },
                        ),
                    )
                    return
                if not item.source_available:
                    raise FileNotFoundError(item.source_object_key)
                source = normalize_provider_image(self._objects.read_image(item.source_object_key))
                generated = await self._generator.generate(
                    prompt=flat_lay_item_prompt(item),
                    images=(source,),
                    size="1728x2304",
                )
                rendered, quality = normalize_flat_lay_output(generated)
                stored = self._objects.write_derived_image(
                    rendered,
                    owner_id=user_id,
                    prefix=f"derived/items/flat-lay/{user_id}/{asset.item_id}",
                )
                await self._presentations.mark_succeeded(
                    user_id=user_id,
                    asset_id=asset_id,
                    output=RenderOutput(
                        object_key=stored.object_key,
                        content_hash=stored.sha256,
                        content_type=stored.content_type,
                    ),
                    provider_trace=generated.provider_trace.with_parameters(
                        capability_id=FLAT_LAY_ITEM_CAPABILITY_ID,
                        capability_alias="image_generation",
                        schema_version=FLAT_LAY_ITEM_SCHEMA_VERSION,
                        canvas="1728x2304",
                        background="#FFFFFF",
                        **quality,
                    ),
                )
                return
            object_key = item.display_object_key or item.source_object_key
            if object_key == item.source_object_key and not item.source_available:
                raise FileNotFoundError(item.source_object_key)
            source = normalize_provider_image(self._objects.read_image(object_key))
            generated = await self._generator.generate(
                prompt=pixel_item_prompt(item),
                images=(source,),
                size="2K",
            )
            rendered, quality = normalize_pixel_card_output(generated, seed=asset.item_id)
            stored = self._objects.write_derived_image(
                rendered,
                owner_id=user_id,
                prefix=f"derived/items/pixel/{user_id}/{asset.item_id}",
            )
            await self._presentations.mark_succeeded(
                user_id=user_id,
                asset_id=asset_id,
                output=RenderOutput(
                    object_key=stored.object_key,
                    content_hash=stored.sha256,
                    content_type=stored.content_type,
                ),
                provider_trace=generated.provider_trace.with_parameters(
                    capability_id=PIXEL_ITEM_CAPABILITY_ID,
                    capability_alias="image_generation",
                    prompt_version=PIXEL_ITEM_PROMPT_VERSION,
                    schema_version=PIXEL_ITEM_SCHEMA_VERSION,
                    requested_canvas="2K square",
                    output_canvas="1024x1024",
                    **quality,
                ),
            )
        except (FileNotFoundError, KeyError):
            await self._presentations.mark_failed(
                user_id=user_id,
                asset_id=asset_id,
                code="source_unavailable",
                message=(
                    "真实单品图暂时不可用, 白底单品图未生成"
                    if asset.kind is ItemPresentationKind.FLAT_LAY_ITEM
                    else "真实单品图暂时不可用, 像素展示图未生成"
                ),
            )
        except RenderProviderError as error:
            if error.retryable and not final_attempt:
                raise RetryableItemPresentationError(str(error)) from error
            await self._presentations.mark_failed(
                user_id=user_id,
                asset_id=asset_id,
                code=error.code,
                message=(
                    "白底单品图暂时未生成, 当前继续展示虚化原图并可重试"
                    if asset.kind is ItemPresentationKind.FLAT_LAY_ITEM
                    else "像素展示图暂时未生成, 真实单品、详情与搭配仍可正常使用"
                ),
            )

    def _render_refined_cutout(
        self,
        item: WardrobeItem,
    ) -> tuple[ImagePayload, dict[str, object]] | None:
        if (
            self._flat_lays is None
            or item.display_object_key is None
            or not _has_refined_segmentation(item.model_metadata)
        ):
            return None
        try:
            display = self._objects.read_image(item.display_object_key)
            if not _has_meaningful_transparency(display):
                return None
            rendered = self._flat_lays.render((display,))
            return normalize_flat_lay_image(rendered.body)
        except (FileNotFoundError, KeyError, CollageRenderError, OSError, ValueError):
            return None


def normalize_flat_lay_output(
    generated: GeneratedImage,
) -> tuple[ImagePayload, dict[str, object]]:
    return normalize_flat_lay_image(generated.body, clean_generated_background=True)


def normalize_pixel_card_output(
    generated: GeneratedImage,
    *,
    seed: UUID | str = "default",
) -> tuple[ImagePayload, dict[str, object]]:
    try:
        with Image.open(BytesIO(generated.body)) as opened:
            image = opened.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise RenderProviderError(
            "pixel_card_image_invalid",
            "Generated pixel card is not decodable",
            retryable=True,
        ) from error
    if image.width != image.height or image.width < 512:
        raise RenderProviderError(
            "pixel_card_ratio_invalid",
            "Generated pixel card must be a square image of at least 512x512",
            retryable=True,
        )

    border = max(8, image.width // 64)
    light = _light_background_mask(image, threshold=218)
    samples = (
        light.crop((0, 0, image.width, border)),
        light.crop((0, image.height - border, image.width, image.height)),
        light.crop((0, border, border, image.height - border)),
        light.crop((image.width - border, border, image.width, image.height - border)),
    )
    border_pixels = sum(sample.width * sample.height for sample in samples)
    light_border_pixels = sum(sample.histogram()[255] for sample in samples)
    light_border_ratio = light_border_pixels / border_pixels
    if light_border_ratio < 0.8:
        raise RenderProviderError(
            "pixel_card_background_invalid",
            "Generated pixel item does not leave a light card-safe border",
            retryable=True,
        )

    halo = _dark_halo_score(image)
    if halo is not None:
        raise RenderProviderError(
            "pixel_card_halo_invalid",
            "Generated pixel item contains a dark halo around the garment",
            retryable=True,
        )

    palette = pixel_card_palette(seed)
    pixelated = image.resize((256, 256), Image.Resampling.BOX)
    pixelated, background_ratio, softened_outline_ratio = _compose_pixel_card(pixelated, palette)
    if background_ratio < 0.15:
        raise RenderProviderError(
            "pixel_card_background_invalid",
            "Generated pixel item does not expose enough connected background for a colorway",
            retryable=True,
        )
    pixelated = pixelated.resize((1024, 1024), Image.Resampling.NEAREST)

    output = BytesIO()
    pixelated.save(output, format="PNG", optimize=True)
    body = output.getvalue()
    return (
        ImagePayload(
            object_key="derived/items/pixel/generated-card.png",
            content_type="image/png",
            body=body,
            sha256=sha256(body).hexdigest(),
        ),
        {
            "quality_gate": "ornate-pixel-card-square-v4",
            "light_border_ratio": round(light_border_ratio, 4),
            "background_palette": palette.name,
            "background_recolored_ratio": round(background_ratio, 4),
            "softened_outline_ratio": round(softened_outline_ratio, 4),
            "outline_color": "#684E38",
            "pixel_grid": "256x256",
            "decorations": "stylecapture-ornate-asymmetric-frame-v4",
            "decoration_count": 6,
        },
    )


def _compose_pixel_card(
    image: Image.Image,
    palette: PixelCardPalette,
) -> tuple[Image.Image, float, float]:
    mask = _connected_soft_background_mask(image, max_channel_distance=170)
    subject_mask = ImageChops.invert(mask)
    image, softened_outline_ratio = _soften_perimeter_outline(image, subject_mask, mask)
    backdrop = _pixel_card_template(image.size, palette)
    recolored = Image.composite(image, backdrop, subject_mask)
    recolored_ratio = mask.histogram()[255] / (image.width * image.height)
    return recolored, recolored_ratio, softened_outline_ratio


def _soften_perimeter_outline(
    image: Image.Image,
    subject_mask: Image.Image,
    background_mask: Image.Image,
) -> tuple[Image.Image, float]:
    luminance = image.convert("L")
    dark = luminance.point(lambda value: 255 if value <= 82 else 0)
    light_subject = ImageChops.multiply(
        subject_mask,
        luminance.point(lambda value: 255 if value >= 118 else 0),
    )
    near_light_subject = light_subject.filter(ImageFilter.MaxFilter(7))
    near_background = background_mask.filter(ImageFilter.MaxFilter(5))
    perimeter_dark = ImageChops.multiply(
        ImageChops.multiply(ImageChops.multiply(subject_mask, dark), near_background),
        near_light_subject,
    )
    softened_pixels = perimeter_dark.histogram()[255]
    if softened_pixels == 0:
        return image, 0.0
    softened = Image.composite(
        Image.new("RGB", image.size, PIXEL_CARD_OUTLINE_COLOR),
        image,
        perimeter_dark,
    )
    return softened, softened_pixels / (image.width * image.height)


def _pixel_card_template(
    size: tuple[int, int],
    palette: PixelCardPalette,
) -> Image.Image:
    card = Image.new("RGB", size, palette.outer)
    draw = ImageDraw.Draw(card)
    width, height = size
    draw.ellipse(
        (
            int(width * 0.145),
            int(height * 0.13),
            int(width * 0.855),
            int(height * 0.84),
        ),
        fill=palette.center,
    )
    _draw_ornate_pixel_frame(draw, size=size, color=palette.frame)
    _draw_asymmetric_pixel_decorations(draw, palette=palette)
    return card


def _rgb_pixel(image: Image.Image, point: tuple[int, int]) -> tuple[int, int, int]:
    return cast(tuple[int, int, int], image.getpixel(point))


def _draw_ornate_pixel_frame(
    draw: ImageDraw.ImageDraw,
    *,
    size: tuple[int, int],
    color: str,
) -> None:
    width, height = size
    base_paths = (
        ((65, 5), (19, 5), (19, 7), (14, 7), (14, 10), (10, 10), (10, 15), (7, 15), (7, 62)),
        ((65, 10), (23, 10), (23, 12), (18, 12), (18, 15), (14, 15), (14, 20), (11, 20), (11, 55)),
    )
    for flip_x, flip_y in ((False, False), (True, False), (False, True), (True, True)):
        for path in base_paths:
            transformed = [
                (
                    width - 1 - x if flip_x else x,
                    height - 1 - y if flip_y else y,
                )
                for x, y in path
            ]
            draw.line(transformed, fill=color, width=1)
        node_x = width - 1 - 10 if flip_x else 8
        node_y = height - 1 - 10 if flip_y else 8
        draw.rectangle((node_x, node_y, node_x + 3, node_y + 3), fill=color)


def _draw_asymmetric_pixel_decorations(
    draw: ImageDraw.ImageDraw,
    *,
    palette: PixelCardPalette,
) -> None:
    pink = "#F2A7BF"
    lilac = "#C8A7F2"
    yellow = "#F3C66F"
    for x, y, color, unit in (
        (47, 34, pink, 2),
        (214, 29, lilac, 1),
        (31, 120, yellow, 2),
        (180, 216, pink, 2),
    ):
        _draw_pixel_sparkle(draw, x=x, y=y, unit=unit, color=color)
    _draw_pixel_heart(draw, x=215, y=117, unit=1, color=pink)
    _draw_pixel_dot(draw, x=43, y=194, unit=2, color=palette.accent)


def _draw_pixel_sparkle(
    draw: ImageDraw.ImageDraw, *, x: int, y: int, unit: int, color: str
) -> None:
    draw.rectangle((x - unit, y - unit * 3, x + unit, y + unit * 3), fill=color)
    draw.rectangle((x - unit * 3, y - unit, x + unit * 3, y + unit), fill=color)


def _draw_pixel_heart(draw: ImageDraw.ImageDraw, *, x: int, y: int, unit: int, color: str) -> None:
    pattern = ("0110110", "1111111", "1111111", "0111110", "0011100", "0001000")
    for row, pixels in enumerate(pattern):
        for column, value in enumerate(pixels):
            if value == "1":
                left = x + (column - 3) * unit
                top = y + row * unit
                draw.rectangle((left, top, left + unit - 1, top + unit - 1), fill=color)


def _draw_pixel_dot(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    unit: int,
    color: str,
) -> None:
    draw.polygon(
        (
            (x - unit, y - unit * 3),
            (x + unit, y - unit * 3),
            (x + unit * 3, y - unit),
            (x + unit * 3, y + unit),
            (x + unit, y + unit * 3),
            (x - unit, y + unit * 3),
            (x - unit * 3, y + unit),
            (x - unit * 3, y - unit),
        ),
        fill=color,
    )


def _draw_pixel_plus(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    unit: int,
    color: str,
) -> None:
    draw.rectangle((x - unit, y - unit * 2, x + unit, y + unit * 2), fill=color)
    draw.rectangle((x - unit * 2, y - unit, x + unit * 2, y + unit), fill=color)


def normalize_flat_lay_image(
    body: bytes,
    *,
    clean_generated_background: bool = False,
) -> tuple[ImagePayload, dict[str, object]]:
    try:
        with Image.open(BytesIO(body)) as opened:
            image = opened.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise RenderProviderError(
            "flat_lay_image_invalid",
            "Generated item image is not decodable",
            retryable=True,
        ) from error
    if image.size != (1728, 2304):
        raise RenderProviderError(
            "flat_lay_ratio_invalid",
            "Generated item image is not the required 1728x2304 portrait canvas",
            retryable=True,
        )

    cleanup: dict[str, object] = {}
    if clean_generated_background:
        image, cleanup = _clean_generated_flat_lay_background(image)

    near_white = _near_white_mask(image, threshold=245)
    border_width = max(1, min(image.size) // 100)
    border_samples = (
        near_white.crop((0, 0, image.width, border_width)),
        near_white.crop((0, image.height - border_width, image.width, image.height)),
        near_white.crop((0, border_width, border_width, image.height - border_width)),
        near_white.crop(
            (image.width - border_width, border_width, image.width, image.height - border_width)
        ),
    )
    border_pixels = sum(sample.width * sample.height for sample in border_samples)
    border_white = sum(sample.histogram()[255] for sample in border_samples)
    border_white_ratio = border_white / border_pixels
    if border_white_ratio < 0.9:
        raise RenderProviderError(
            "flat_lay_background_invalid",
            "Generated item image does not have a clean white border",
            retryable=True,
        )

    if clean_generated_background:
        normalized = image
        exact_white_mask = _near_white_mask(normalized, threshold=255)
        pure_white_ratio = exact_white_mask.histogram()[255] / (image.width * image.height)
        normalization_metrics = cleanup
        minimum_white_ratio = 0.55
    else:
        connected_background_mask = _connected_soft_background_mask(
            image,
            max_channel_distance=170,
        )
        exact_white_mask = _near_white_mask(image, threshold=248)
        clean_background_mask = ImageChops.lighter(
            exact_white_mask,
            connected_background_mask,
        )
        normalized = Image.composite(
            Image.new("RGB", image.size, "white"),
            image,
            clean_background_mask,
        )
        pure_white_ratio = clean_background_mask.histogram()[255] / (image.width * image.height)
        normalization_metrics = {"background_cleaned_ratio": round(pure_white_ratio, 4)}
        minimum_white_ratio = 0.5
    if pure_white_ratio < minimum_white_ratio:
        raise RenderProviderError(
            "flat_lay_background_invalid",
            "Generated item image does not contain enough white background",
            retryable=True,
        )
    halo = _dark_halo_score(image)
    if halo is not None:
        raise RenderProviderError(
            "flat_lay_halo_invalid",
            "Generated item image contains a dark halo around the garment",
            retryable=True,
        )
    output = BytesIO()
    normalized.save(output, format="PNG", optimize=True)
    body = output.getvalue()
    return (
        ImagePayload(
            object_key="derived/items/flat-lay/generated.png",
            content_type="image/png",
            body=body,
            sha256=sha256(body).hexdigest(),
        ),
        {
            "quality_gate": ("pure-white-3x4-v2" if clean_generated_background else "white-3x4-v1"),
            "border_white_ratio": round(border_white_ratio, 4),
            "pure_white_ratio": round(pure_white_ratio, 4),
            **normalization_metrics,
        },
    )


def _clean_generated_flat_lay_background(
    image: Image.Image,
) -> tuple[Image.Image, dict[str, object]]:
    width, height = image.size
    analysis_scale = 4
    analysis_size = (width // analysis_scale, height // analysis_scale)
    analysis = image.resize(analysis_size, Image.Resampling.NEAREST)
    definite_foreground = ImageChops.invert(
        _near_neutral_light_mask(
            analysis,
            minimum_channel=225,
            maximum_chroma=30,
        )
    )
    foreground_barrier = definite_foreground.filter(ImageFilter.MaxFilter(9))
    open_background = ImageChops.invert(foreground_barrier)
    connected_background = open_background.copy()
    analysis_width, analysis_height = analysis.size
    step_x = max(1, analysis_width // 8)
    step_y = max(1, analysis_height // 8)
    seeds = (
        [(x, 0) for x in range(0, analysis_width, step_x)]
        + [(x, analysis_height - 1) for x in range(0, analysis_width, step_x)]
        + [(0, y) for y in range(0, analysis_height, step_y)]
        + [(analysis_width - 1, y) for y in range(0, analysis_height, step_y)]
    )
    for point in seeds:
        if connected_background.getpixel(point) == 255:
            ImageDraw.floodfill(connected_background, point, 128, thresh=0)
    external_background = connected_background.point(lambda value: 255 if value == 128 else 0)
    subject_protection_analysis = ImageChops.invert(external_background)
    subject_bbox = subject_protection_analysis.getbbox()
    if subject_bbox is None:
        raise RenderProviderError(
            "flat_lay_subject_invalid",
            "Generated item image does not contain a detectable centered product",
            retryable=True,
        )

    left, top, right, bottom = subject_bbox
    if right - left > analysis_width * 0.9 or bottom - top > analysis_height * 0.9:
        raise RenderProviderError(
            "flat_lay_background_invalid",
            "Generated item does not leave enough clean background around the product",
            retryable=True,
        )
    protected_bbox = (
        left * analysis_scale,
        top * analysis_scale,
        min(width, right * analysis_scale),
        min(height, bottom * analysis_scale),
    )
    subject_protection = subject_protection_analysis.resize(
        image.size,
        Image.Resampling.NEAREST,
    )
    full_resolution_foreground = ImageChops.invert(
        _near_neutral_light_mask(
            image,
            minimum_channel=225,
            maximum_chroma=30,
        )
    )
    subject_protection = ImageChops.lighter(
        subject_protection,
        full_resolution_foreground,
    )
    background_mask = ImageChops.invert(subject_protection)
    cleaned = Image.composite(
        Image.new("RGB", image.size, "white"),
        image,
        background_mask,
    )

    changed = (
        ImageChops.difference(cleaned, image)
        .convert("L")
        .point(lambda value: 255 if value > 0 else 0)
    )
    total_pixels = width * height
    return cleaned, {
        "background_cleanup": "silhouette-protected-pure-white-v2",
        "background_analysis_grid": f"{analysis_width}x{analysis_height}",
        "background_changed_ratio": round(changed.histogram()[255] / total_pixels, 4),
        "protected_product_bbox": ",".join(str(value) for value in protected_bbox),
    }


def _near_neutral_light_mask(
    image: Image.Image,
    *,
    minimum_channel: int,
    maximum_chroma: int,
) -> Image.Image:
    red, green, blue = image.split()
    brightest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    darkest = ImageChops.darker(ImageChops.darker(red, green), blue)
    light = darkest.point(lambda value: 255 if value >= minimum_channel else 0)
    chroma = ImageChops.subtract(brightest, darkest)
    neutral = chroma.point(lambda value: 255 if value <= maximum_chroma else 0)
    return ImageChops.multiply(light, neutral)


def _near_white_mask(image: Image.Image, *, threshold: int) -> Image.Image:
    channels = image.split()
    masks = [channel.point(lambda value: 255 if value >= threshold else 0) for channel in channels]
    return ImageChops.multiply(ImageChops.multiply(masks[0], masks[1]), masks[2])


def _light_background_mask(image: Image.Image, *, threshold: int) -> Image.Image:
    return image.convert("L").point(lambda value: 255 if value >= threshold else 0)


def _connected_soft_background_mask(
    image: Image.Image,
    *,
    max_channel_distance: int,
) -> Image.Image:
    rgb = image.convert("RGB")
    preview = rgb.resize((64, 64), Image.Resampling.BOX)
    border_pixels: list[tuple[int, int, int]] = (
        [_rgb_pixel(preview, (x, 0)) for x in range(preview.width)]
        + [_rgb_pixel(preview, (x, preview.height - 1)) for x in range(preview.width)]
        + [_rgb_pixel(preview, (0, y)) for y in range(1, preview.height - 1)]
        + [_rgb_pixel(preview, (preview.width - 1, y)) for y in range(1, preview.height - 1)]
    )
    background = (
        int(median(pixel[0] for pixel in border_pixels)),
        int(median(pixel[1] for pixel in border_pixels)),
        int(median(pixel[2] for pixel in border_pixels)),
    )
    channels = rgb.split()
    differences = [
        ImageChops.difference(channel, Image.new("L", rgb.size, background[index]))
        for index, channel in enumerate(channels)
    ]
    distance = ImageChops.lighter(
        ImageChops.lighter(differences[0], differences[1]), differences[2]
    )
    close_to_edge_color = distance.point(lambda value: 255 if value <= max_channel_distance else 0)
    light_enough = _light_background_mask(rgb, threshold=82)
    red, green, blue = channels
    chroma = ImageChops.lighter(
        ImageChops.lighter(
            ImageChops.difference(red, green),
            ImageChops.difference(red, blue),
        ),
        ImageChops.difference(green, blue),
    )
    low_chroma = chroma.point(lambda value: 255 if value <= 54 else 0)
    candidates = ImageChops.multiply(
        ImageChops.multiply(close_to_edge_color, light_enough),
        low_chroma,
    )

    connected = candidates.copy()
    step = max(1, min(rgb.size) // 16)
    seeds = (
        [(x, 0) for x in range(0, rgb.width, step)]
        + [(x, rgb.height - 1) for x in range(0, rgb.width, step)]
        + [(0, y) for y in range(0, rgb.height, step)]
        + [(rgb.width - 1, y) for y in range(0, rgb.height, step)]
    )
    for point in seeds:
        if connected.getpixel(point) == 255:
            ImageDraw.floodfill(connected, point, 128, thresh=0)
    return connected.point(lambda value: 255 if value == 128 else 0)


def _dark_halo_score(image: Image.Image) -> dict[str, object] | None:
    """Detect thin dark rings on otherwise light product-card backgrounds.

    The check deliberately ignores large dark subjects. It only fires when dark
    pixels form a narrow outline on three or more sides of a larger non-dark
    foreground, which matches the black-ring artifact without rejecting black
    garments.
    """
    width, height = image.size
    if width < 128 or height < 128:
        return None
    sample_width = 256
    sample_height = max(128, round(height * sample_width / width))
    sample = image.resize((sample_width, sample_height), Image.Resampling.BOX)
    luminance = sample.convert("L")
    foreground = luminance.point(lambda value: 255 if value < 245 else 0)
    bbox = foreground.getbbox()
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    foreground_area = foreground.crop(bbox).histogram()[255]
    if foreground_area <= 0:
        return None

    dark = luminance.point(lambda value: 255 if value <= 72 else 0)
    dark_area = dark.crop(bbox).histogram()[255]
    dark_ratio = dark_area / foreground_area
    if dark_ratio < 0.015 or dark_ratio > 0.28:
        return None

    inset = max(3, min(right - left, bottom - top) // 18)
    side_regions = {
        "left": (left, top, min(right, left + inset), bottom),
        "right": (max(left, right - inset), top, right, bottom),
        "top": (left, top, right, min(bottom, top + inset)),
        "bottom": (left, max(top, bottom - inset), right, bottom),
    }
    touched_sides = 0
    for region in side_regions.values():
        region_width = max(0, region[2] - region[0])
        region_height = max(0, region[3] - region[1])
        if region_width == 0 or region_height == 0:
            continue
        side_ratio = dark.crop(region).histogram()[255] / (region_width * region_height)
        if side_ratio >= 0.18:
            touched_sides += 1
    if touched_sides < 3:
        return None

    core_inset = max(inset * 2, 8)
    core = (
        min(right, left + core_inset),
        min(bottom, top + core_inset),
        max(left, right - core_inset),
        max(top, bottom - core_inset),
    )
    if core[0] >= core[2] or core[1] >= core[3]:
        return None
    core_area = (core[2] - core[0]) * (core[3] - core[1])
    core_dark_ratio = dark.crop(core).histogram()[255] / core_area
    if core_dark_ratio >= dark_ratio * 0.7:
        return None
    return {
        "dark_ratio": round(dark_ratio, 4),
        "touched_sides": touched_sides,
        "core_dark_ratio": round(core_dark_ratio, 4),
    }


def _has_refined_segmentation(metadata: Mapping[str, object]) -> bool:
    direct = metadata.get("segmentation")
    if isinstance(direct, Mapping) and direct.get("representation") == "refined_mask":
        return True
    normalization = metadata.get("normalization")
    if not isinstance(normalization, Mapping):
        return False
    segmentation = normalization.get("segmentation")
    return (
        isinstance(segmentation, Mapping) and segmentation.get("representation") == "refined_mask"
    )


def _has_meaningful_transparency(payload: ImagePayload) -> bool:
    try:
        with Image.open(BytesIO(payload.body)) as opened:
            if "A" not in opened.getbands():
                return False
            alpha = opened.getchannel("A")
            histogram = alpha.histogram()
            transparent_or_soft = sum(histogram[:250])
            return transparent_or_soft / (alpha.width * alpha.height) >= 0.05
    except (UnidentifiedImageError, OSError, ValueError):
        return False
