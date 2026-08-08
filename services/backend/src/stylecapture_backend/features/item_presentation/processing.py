from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from io import BytesIO
from typing import Protocol
from uuid import UUID

from PIL import Image, ImageChops, ImageDraw, UnidentifiedImageError
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


def pixel_item_prompt(item: WardrobeItem) -> str:
    fields = item.attributes.fields
    name = _field_text(fields, "description", "这件单品")
    category = _field_text(fields, "category", "服装")
    subcategory = _field_text(fields, "subcategory", "")
    colors = _field_text(fields, "colors", "")
    return f"""
只识别并提取参考图中的目标单品“{name}”(类别 {category}/{subcategory}, 主色 {colors}),
把它转换为 StyleCapture 统一的复古像素收藏卡。严格输出 1:1 正方形 2048x2048。

主体规则: 只出现一个目标单品; 鞋只保留一双配对鞋; 目标明确为一组配饰时才保留整组。
单品正面居中、完整可见、不裁切、不拉伸, 占画面约 60% 至 72%, 四周留出装饰安全区。
忠实保留原单品的主色、轮廓、图案、领口、袖型、褶皱、吊带和结构, 不新增看不见的部件。

像素风规则: 使用清晰硬边的 16-bit / 32-bit 商品像素画, 轮廓由深一档同色像素描边,
内部用有限色阶表达材质和褶皱; 像素块大小一致, 禁止局部写实、局部像素的混合风格,
禁止模糊、抗锯齿、油画、3D 渲染、照片质感、矢量插画或平滑渐变。

卡片背景: 很浅的粉白色背景, 中央可有低对比度圆形淡粉光晕。不要生成边框、爱心、星星或文字,
这些装饰由后端统一叠加。禁止人物、人体、皮肤、头发、模特、衣架、场景、其他衣物、品牌、
水印、标签、价格、文字、拼贴、分镜、多个候选和额外道具。
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

生成独立电商商品白底图: 严格竖版 3:4, 输出 1728x2304; 背景必须是均匀纯白色;
目标单品居中、完整轮廓全部可见、四周保留充足白边, 不裁切、不拉伸、不压扁。
使用正面或最利于识别的轻微俯视角度, 写实高分辨率产品摄影, 忠实保留原图中
实际可见的颜色、版型、材质、褶裥、纽扣、吊带、孔洞和结构。

不要出现其他衣物、整套穿搭、人物、人体部位、皮肤、头发、眼镜、手机、背景、
游客、衣架、模特、文字、品牌、水印、边框或道具。不要臆造看不见的花纹和结构。
仅允许极浅、紧贴物体的自然接触阴影; 禁止灰色矩形底、大面积阴影、插画、剪纸、
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
                size="2048x2048",
            )
            rendered, quality = normalize_pixel_card_output(generated)
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
                    requested_canvas="2048x2048",
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
    return normalize_flat_lay_image(generated.body)


def normalize_pixel_card_output(
    generated: GeneratedImage,
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
    if image.size != (2048, 2048):
        raise RenderProviderError(
            "pixel_card_ratio_invalid",
            "Generated pixel card is not the required 2048x2048 square canvas",
            retryable=True,
        )

    border = 32
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

    pixelated = image.resize((256, 256), Image.Resampling.BOX)
    pixelated = pixelated.quantize(
        colors=96,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    ).convert("RGB")
    pixelated = pixelated.resize((1024, 1024), Image.Resampling.NEAREST)
    _draw_pixel_card_decorations(pixelated)

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
            "quality_gate": "pastel-pixel-card-square-v1",
            "light_border_ratio": round(light_border_ratio, 4),
            "pixel_grid": "256x256",
            "palette_colors": 96,
            "decorations": "stylecapture-pastel-frame-v1",
        },
    )


def _draw_pixel_card_decorations(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)
    pink = "#F7A8C4"
    pale_pink = "#FBC7D9"
    lilac = "#C8A7F2"
    yellow = "#F6CE7A"

    _draw_corner_frame(draw, color=pale_pink)
    for x, y, color, unit in (
        (148, 180, pink, 8),
        (862, 166, lilac, 8),
        (130, 500, yellow, 10),
        (880, 520, pink, 8),
        (212, 820, lilac, 6),
        (780, 824, yellow, 6),
    ):
        _draw_pixel_sparkle(draw, x=x, y=y, unit=unit, color=color)
    _draw_pixel_heart(draw, x=126, y=710, unit=8, color=pink)
    _draw_pixel_heart(draw, x=858, y=690, unit=8, color=pink)


def _draw_corner_frame(draw: ImageDraw.ImageDraw, *, color: str) -> None:
    width = 4
    segments = (
        ((40, 40), (250, 40)),
        ((774, 40), (984, 40)),
        ((40, 984), (250, 984)),
        ((774, 984), (984, 984)),
        ((40, 40), (40, 250)),
        ((40, 774), (40, 984)),
        ((984, 40), (984, 250)),
        ((984, 774), (984, 984)),
    )
    for start, end in segments:
        draw.line((start, end), fill=color, width=width)
    for x, y, sx, sy in (
        (40, 40, 1, 1),
        (984, 40, -1, 1),
        (40, 984, 1, -1),
        (984, 984, -1, -1),
    ):
        draw.line((x, y, x + sx * 28, y), fill=color, width=8)
        draw.line((x, y, x, y + sy * 28), fill=color, width=8)
        draw.rectangle(
            (
                x + sx * 20 - 4,
                y + sy * 20 - 4,
                x + sx * 20 + 4,
                y + sy * 20 + 4,
            ),
            fill=color,
        )


def _draw_pixel_sparkle(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    unit: int,
    color: str,
) -> None:
    draw.rectangle((x - unit, y - unit * 3, x + unit, y + unit * 3), fill=color)
    draw.rectangle((x - unit * 3, y - unit, x + unit * 3, y + unit), fill=color)
    draw.rectangle((x - unit * 2, y - unit * 2, x + unit * 2, y + unit * 2), fill=color)


def _draw_pixel_heart(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    unit: int,
    color: str,
) -> None:
    pattern = (
        "0110110",
        "1111111",
        "1111111",
        "0111110",
        "0011100",
        "0001000",
    )
    for row, pixels in enumerate(pattern):
        for column, value in enumerate(pixels):
            if value == "1":
                left = x + (column - 3) * unit
                top = y + row * unit
                draw.rectangle((left, top, left + unit - 1, top + unit - 1), fill=color)


def normalize_flat_lay_image(
    body: bytes,
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

    exact_white_mask = _near_white_mask(image, threshold=248)
    normalized = Image.composite(
        Image.new("RGB", image.size, "white"),
        image,
        exact_white_mask,
    )
    pure_white_ratio = exact_white_mask.histogram()[255] / (image.width * image.height)
    if pure_white_ratio < 0.5:
        raise RenderProviderError(
            "flat_lay_background_invalid",
            "Generated item image does not contain enough white background",
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
            "quality_gate": "white-3x4-v1",
            "border_white_ratio": round(border_white_ratio, 4),
            "pure_white_ratio": round(pure_white_ratio, 4),
        },
    )


def _near_white_mask(image: Image.Image, *, threshold: int) -> Image.Image:
    channels = image.split()
    masks = [channel.point(lambda value: 255 if value >= threshold else 0) for channel in channels]
    return ImageChops.multiply(ImageChops.multiply(masks[0], masks[1]), masks[2])


def _light_background_mask(image: Image.Image, *, threshold: int) -> Image.Image:
    return image.convert("L").point(lambda value: 255 if value >= threshold else 0)


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
