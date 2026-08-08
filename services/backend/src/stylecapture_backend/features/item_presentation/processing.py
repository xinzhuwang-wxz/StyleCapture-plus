from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from io import BytesIO
from typing import Protocol
from uuid import UUID

from PIL import Image, ImageChops, UnidentifiedImageError
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
从参考图中只识别并提取目标商品“{name}” (类别 {category}/{subcategory}, 主色 {colors}),
将这个目标商品转换为 StyleCapture 可爱像素风商品展示图。
必须是电商商品抠图式构图: 只出现一个目标单品; 若目标本来是一双鞋, 则只出现一双配对鞋;
若目标明确是配饰组, 才可保留该组配饰。不要画模特、人体、内搭、裤子、包、货架、商店、
街景、其他衣服或其他鞋, 不要生成完整穿搭。
忠实保留目标单品的主色、材质、版型、图案和关键细节, 使用干净浅色或透明感背景,
居中完整展示。禁止文字、品牌、水印、拼贴、分镜、多个候选或额外道具。
输出像素风, 但不要改变它作为真实衣橱资产的类别和辨识度。
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
                size="2K",
            )
            stored = self._objects.write_derived_image(
                ImagePayload(
                    object_key=f"derived/items/pixel/{asset.item_id}",
                    content_type=generated.content_type,
                    body=generated.body,
                    sha256=generated.sha256,
                ),
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
