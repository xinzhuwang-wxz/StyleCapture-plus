from __future__ import annotations

from hashlib import sha256
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.capture.ports import StoredObject
from stylecapture_backend.features.look.domain import LookComponentStatus, LookDetail
from stylecapture_backend.features.look.ports import LookRepository
from stylecapture_backend.features.render.application import RenderApplication
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderArtifactStatus,
    RenderOutput,
    RenderProviderTrace,
)
from stylecapture_backend.features.render.ports import (
    CollageRenderer,
    CollageRenderError,
    GeneratedImage,
    RenderArtifactRepository,
    RenderProviderError,
)
from stylecapture_backend.features.wardrobe.domain import WardrobeItem


class RetryableRenderError(RuntimeError):
    pass


class RenderObjectStore(Protocol):
    def describe(self, object_key: str) -> StoredObject: ...

    def read_image(self, object_key: str) -> ImagePayload: ...

    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload: ...


class PixelGenerator(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        images: tuple[ImagePayload, ...],
        size: str = "1024x1024",
    ) -> GeneratedImage: ...


class TryOnGenerator(Protocol):
    async def try_on(
        self,
        *,
        model_image: ImagePayload,
        garment_image: ImagePayload,
        category: str = "auto",
        mode: str = "balanced",
    ) -> GeneratedImage: ...


class WardrobeReader(Protocol):
    async def get_for_user(
        self,
        item_id: UUID,
        user_id: UUID,
    ) -> WardrobeItem | None: ...


class RenderProcessor:
    def __init__(
        self,
        *,
        artifacts: RenderArtifactRepository,
        renders: RenderApplication,
        looks: LookRepository,
        wardrobe: WardrobeReader,
        objects: RenderObjectStore,
        collages: CollageRenderer,
        pixel_generator: PixelGenerator | None,
        try_on_generator: TryOnGenerator | None,
        fixed_model_object_key: str | None,
    ) -> None:
        self._artifacts = artifacts
        self._renders = renders
        self._looks = looks
        self._wardrobe = wardrobe
        self._objects = objects
        self._collages = collages
        self._pixel_generator = pixel_generator
        self._try_on_generator = try_on_generator
        self._fixed_model_object_key = (
            fixed_model_object_key.strip() if fixed_model_object_key else None
        )

    async def process(self, *, user_id: UUID, artifact_id: UUID) -> None:
        artifact = await self._artifacts.get_for_user(
            user_id=user_id,
            artifact_id=artifact_id,
        )
        if artifact is None:
            return
        if artifact.status in {
            RenderArtifactStatus.SUCCEEDED,
            RenderArtifactStatus.DEGRADED,
        }:
            return
        if artifact.kind is RenderArtifactKind.COLLAGE:
            await self._process_collage(artifact)
            return

        fallback = await self._fallback_artifact(artifact)
        if fallback is None or fallback.output is None:
            raise RetryableRenderError("render source collage is not ready")
        if artifact.kind is RenderArtifactKind.PIXEL_COVER:
            await self._process_pixel_cover(artifact, fallback)
            return
        await self._process_try_on(artifact, fallback)

    async def _process_collage(self, artifact: RenderArtifact) -> None:
        try:
            detail, item_images = await self._look_item_images(artifact)
            await self._renders.mark_running(
                user_id=artifact.user_id,
                artifact_id=artifact.id,
                provider_trace=RenderProviderTrace(
                    provider="deterministic",
                    model="pillow-collage-v1",
                    parameters={
                        "component_count": len(item_images),
                        "look_version": detail.look.updated_at.isoformat(),
                    },
                ),
            )
            rendered = self._collages.render(item_images)
            await self._store_success(artifact, rendered)
        except CollageRenderError as error:
            await self._renders.mark_failed(
                user_id=artifact.user_id,
                artifact_id=artifact.id,
                code="collage_input_invalid",
                message=str(error),
            )
        except (FileNotFoundError, KeyError, OSError) as error:
            await self._renders.mark_failed(
                user_id=artifact.user_id,
                artifact_id=artifact.id,
                code="collage_source_unavailable",
                message="A real Item image is temporarily unavailable",
            )
            raise RetryableRenderError("collage source image is unavailable") from error

    async def _process_pixel_cover(
        self,
        artifact: RenderArtifact,
        fallback: RenderArtifact,
    ) -> None:
        if self._pixel_generator is None:
            await self._degrade(artifact, fallback, "像素生成服务未配置。展示真实单品拼贴")
            return
        source = self._objects.read_image(fallback.output.object_key)  # type: ignore[union-attr]
        await self._renders.mark_running(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
        )
        try:
            generated = await self._pixel_generator.generate(
                prompt=(
                    "把参考穿搭转换为 StyleCapture 可爱像素角色封面。保持每件衣服的"
                    "颜色、轮廓、层次和搭配关系。全身正面。浅色纯净背景。不添加文字、"
                    "品牌、水印或额外服饰。"
                ),
                images=(source,),
                size="2K",
            )
            await self._record_provider_and_store(artifact, generated)
        except (RenderProviderError, ValueError):
            await self._degrade(artifact, fallback, "像素生成暂不可用。展示真实单品拼贴")
            return

    async def _process_try_on(
        self,
        artifact: RenderArtifact,
        fallback: RenderArtifact,
    ) -> None:
        if self._try_on_generator is None or self._fixed_model_object_key is None:
            await self._degrade(artifact, fallback, "固定模特试穿未配置。展示真实单品拼贴")
            return
        try:
            model_image = self._objects.read_image(self._fixed_model_object_key)
            _, item_assets = await self._look_item_assets(artifact)
        except (FileNotFoundError, KeyError):
            await self._degrade(artifact, fallback, "试穿输入不可用。展示真实单品拼贴")
            return

        garments = tuple(
            (category, image)
            for role, image in item_assets
            if (category := _try_on_category(role)) is not None
        )
        await self._renders.mark_running(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
        )
        current = model_image
        last_generated: GeneratedImage | None = None
        try:
            for category, garment in garments:
                last_generated = await self._try_on_generator.try_on(
                    model_image=current,
                    garment_image=garment,
                    category=category,
                    mode="balanced",
                )
                current = _generated_payload(last_generated)
        except (RenderProviderError, ValueError):
            await self._degrade(artifact, fallback, "试穿生成暂不可用。展示真实单品拼贴")
            return
        if last_generated is None:
            await self._degrade(artifact, fallback, "没有可试穿单品。展示真实单品拼贴")
            return
        trace = RenderProviderTrace(
            provider=last_generated.provider_trace.provider,
            model=last_generated.provider_trace.model,
            parameters={
                **dict(last_generated.provider_trace.parameters),
                "garment_count": len(garments),
                "personalization": "fixed_model",
            },
        )
        await self._renders.mark_running(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
            provider_trace=trace,
        )
        await self._store_success(artifact, _generated_payload(last_generated))

    async def _look_item_images(
        self,
        artifact: RenderArtifact,
    ) -> tuple[LookDetail, tuple[ImagePayload, ...]]:
        detail, assets = await self._look_item_assets(artifact)
        return detail, tuple(image for _role, image in assets)

    async def _look_item_assets(
        self,
        artifact: RenderArtifact,
    ) -> tuple[LookDetail, tuple[tuple[str | None, ImagePayload], ...]]:
        detail = await self._looks.get_detail_for_user(
            artifact.look_id,
            artifact.user_id,
        )
        if detail is None:
            raise CollageRenderError("render Look does not exist")
        ready = sorted(
            (
                component
                for component in detail.components
                if component.status is LookComponentStatus.READY and component.item_id is not None
            ),
            key=lambda component: component.display_order,
        )
        assets: list[tuple[str | None, ImagePayload]] = []
        for component in ready[:6]:
            item = await self._wardrobe.get_for_user(
                component.item_id,  # type: ignore[arg-type]
                artifact.user_id,
            )
            if item is None:
                raise CollageRenderError("render Look references a missing Item")
            object_key = item.display_object_key or (
                item.source_object_key if item.source_available else None
            )
            if object_key is None:
                raise CollageRenderError("render Item has no available display image")
            assets.append((component.role, self._objects.read_image(object_key)))
        return detail, tuple(assets)

    async def _fallback_artifact(
        self,
        artifact: RenderArtifact,
    ) -> RenderArtifact | None:
        if artifact.source_artifact_id is None:
            return None
        fallback = await self._artifacts.get_for_user(
            user_id=artifact.user_id,
            artifact_id=artifact.source_artifact_id,
        )
        if fallback is None or fallback.look_id != artifact.look_id:
            return None
        if fallback.kind is not RenderArtifactKind.COLLAGE:
            return None
        if fallback.status is not RenderArtifactStatus.SUCCEEDED:
            return None
        return fallback

    async def _record_provider_and_store(
        self,
        artifact: RenderArtifact,
        generated: GeneratedImage,
    ) -> None:
        await self._renders.mark_running(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
            provider_trace=generated.provider_trace,
        )
        await self._store_success(artifact, _generated_payload(generated))

    async def _store_success(
        self,
        artifact: RenderArtifact,
        image: ImagePayload,
    ) -> None:
        stored = self._objects.write_derived_image(
            image,
            owner_id=artifact.user_id,
            prefix="derived/renders",
        )
        await self._renders.mark_succeeded(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
            output=RenderOutput(
                object_key=stored.object_key,
                content_hash=stored.sha256,
                content_type=stored.content_type,
            ),
        )

    async def _degrade(
        self,
        artifact: RenderArtifact,
        fallback: RenderArtifact,
        reason: str,
    ) -> None:
        await self._renders.degrade_to_fallback(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
            fallback_artifact_id=fallback.id,
            reason=reason,
        )


def _generated_payload(generated: GeneratedImage) -> ImagePayload:
    content_hash = sha256(generated.body).hexdigest()
    if content_hash != generated.sha256:
        raise ValueError("render provider output hash does not match its bytes")
    return ImagePayload(
        object_key=f"derived/renders/pending-{content_hash}.png",
        content_type=generated.content_type,
        body=generated.body,
        sha256=content_hash,
    )


def _try_on_category(role: str | None) -> str | None:
    if role in {"tops", "outerwear"}:
        return "tops"
    if role == "bottoms":
        return "bottoms"
    if role == "dresses":
        return "one-pieces"
    return None
