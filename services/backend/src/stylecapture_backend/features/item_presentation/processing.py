from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.item_presentation.application import (
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
from stylecapture_backend.features.render.domain import RenderOutput
from stylecapture_backend.features.render.ports import GeneratedImage, RenderProviderError
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
    ) -> None:
        self._presentations = presentations
        self._wardrobe = wardrobe
        self._objects = objects
        self._generator = generator

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
        if asset.kind is not ItemPresentationKind.PIXEL_ITEM:
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
                message="真实单品图暂时不可用, 像素展示图未生成",
            )
        except RenderProviderError as error:
            if error.retryable and not final_attempt:
                raise RetryableItemPresentationError(str(error)) from error
            await self._presentations.mark_failed(
                user_id=user_id,
                asset_id=asset_id,
                code=error.code,
                message="像素展示图暂时未生成, 真实单品、详情与搭配仍可正常使用",
            )
