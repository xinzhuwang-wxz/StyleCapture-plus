from __future__ import annotations

from hashlib import sha256
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.capture.ports import StoredObject
from stylecapture_backend.features.item_presentation.domain import ItemPresentationStatus
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
from stylecapture_backend.features.render.pixel_card_style import (
    PIXEL_CARD_GUIDANCE_SCALE,
    PIXEL_CARD_SEED,
    PIXEL_CARD_STYLE_REFERENCE_VERSION,
    load_pixel_card_style_references,
    pixel_card_style_reference_hashes,
)
from stylecapture_backend.features.render.ports import (
    CollageRenderer,
    CollageRenderError,
    GeneratedImage,
    PixelSpriteExtractionError,
    PixelSpriteExtractor,
    RenderArtifactRepository,
    RenderProviderError,
)
from stylecapture_backend.features.render.prompt_contracts import (
    PIXEL_COVER_CAPABILITY_ID,
    PIXEL_COVER_OUTPUT_SIZE,
    PIXEL_COVER_PROMPT,
    PIXEL_COVER_PROMPT_VERSION,
    PIXEL_COVER_SCHEMA_VERSION,
    TRY_ON_CAPABILITY_ID,
    TRY_ON_OUTPUT_SIZE,
    TRY_ON_PIPELINE_VERSION,
    TRY_ON_PROMPT,
    TRY_ON_PROMPT_VERSION,
    TRY_ON_SCHEMA_VERSION,
)
from stylecapture_backend.features.wardrobe.domain import WardrobeItem
from stylecapture_backend.platform.image_normalization import normalize_provider_image


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
        seed: int | None = None,
        guidance_scale: float | None = None,
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


class AuditedTryOnGenerator(Protocol):
    async def try_on(
        self,
        *,
        model_image: ImagePayload,
        outfit_board: ImagePayload,
    ) -> GeneratedImage: ...


class WardrobeReader(Protocol):
    async def get_for_user(
        self,
        item_id: UUID,
        user_id: UUID,
    ) -> WardrobeItem | None: ...


class ItemFlatLayView(Protocol):
    @property
    def status(self) -> ItemPresentationStatus: ...

    @property
    def object_key(self) -> str | None: ...


class ItemFlatLayReader(Protocol):
    async def get_current_flat_lay_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
    ) -> ItemFlatLayView | None: ...


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
        item_presentations: ItemFlatLayReader | None = None,
        pixel_sprite_extractor: PixelSpriteExtractor | None = None,
        audited_try_on_generator: AuditedTryOnGenerator | None = None,
    ) -> None:
        self._artifacts = artifacts
        self._renders = renders
        self._looks = looks
        self._wardrobe = wardrobe
        self._objects = objects
        self._collages = collages
        self._pixel_generator = pixel_generator
        self._try_on_generator = try_on_generator
        self._audited_try_on_generator = audited_try_on_generator
        self._fixed_model_object_key = (
            fixed_model_object_key.strip() if fixed_model_object_key else None
        )
        self._item_presentations = item_presentations
        self._pixel_sprite_extractor = pixel_sprite_extractor

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
            if (
                artifact.status is RenderArtifactStatus.SUCCEEDED
                and artifact.kind is RenderArtifactKind.PIXEL_COVER
                and artifact.output is not None
                and artifact.sprite_output is None
                and not artifact.sprite_extraction_failed
            ):
                await self._backfill_pixel_sprite(artifact)
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
                    model="pillow-collage-v6-centered-square-cutout",
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
        content_object_key = fallback.output.object_key  # type: ignore[union-attr]
        input_source_kind = fallback.kind.value
        if fallback.kind is RenderArtifactKind.COLLAGE:
            detail = await self._looks.get_detail_for_user(
                artifact.look_id,
                artifact.user_id,
            )
            if detail is not None and detail.look.display_object_key is not None:
                # A Look's original image is the strongest source of truth for a pixel
                # character. Do not also send its collage: isolated Item layouts are
                # easily copied as floating background ornaments.
                content_object_key = detail.look.display_object_key
                input_source_kind = "look_display"
        try:
            content_source = normalize_provider_image(
                self._objects.read_image(content_object_key)
            )
        except (FileNotFoundError, KeyError):
            if input_source_kind != "look_display":
                raise
            # A stale Look display pointer must not discard an otherwise ready collage.
            content_source = normalize_provider_image(
                self._objects.read_image(
                    fallback.output.object_key  # type: ignore[union-attr]
                )
            )
            input_source_kind = fallback.kind.value
        await self._renders.mark_running(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
        )
        try:
            generated = await self._pixel_generator.generate(
                prompt=PIXEL_COVER_PROMPT,
                images=(content_source, *load_pixel_card_style_references()),
                size=PIXEL_COVER_OUTPUT_SIZE,
                seed=PIXEL_CARD_SEED,
                guidance_scale=PIXEL_CARD_GUIDANCE_SCALE,
            )
            await self._record_provider_and_store(
                artifact,
                generated,
                capability_id=PIXEL_COVER_CAPABILITY_ID,
                prompt_version=PIXEL_COVER_PROMPT_VERSION,
                schema_version=PIXEL_COVER_SCHEMA_VERSION,
                extra_parameters={
                    "input_source_kind": input_source_kind,
                    "content_image_count": 1,
                    "style_reference_version": PIXEL_CARD_STYLE_REFERENCE_VERSION,
                    "style_reference_hashes": pixel_card_style_reference_hashes(),
                },
            )
        except (RenderProviderError, ValueError):
            await self._degrade(artifact, fallback, "像素生成暂不可用。展示真实单品拼贴")
            return

    async def _process_try_on(
        self,
        artifact: RenderArtifact,
        fallback: RenderArtifact,
    ) -> None:
        model_object_key = artifact.subject_object_key or self._fixed_model_object_key
        if model_object_key is None:
            await self._degrade(artifact, fallback, "请上传全身照后生成真人试穿。展示真实单品拼贴")
            return
        try:
            model_image = normalize_provider_image(self._objects.read_image(model_object_key))
            _, item_assets = await self._look_item_assets(artifact)
        except (FileNotFoundError, KeyError):
            await self._degrade(artifact, fallback, "试穿输入不可用。展示真实单品拼贴")
            return

        dedicated_garments = tuple(
            (category, image)
            for role, image in item_assets
            if (category := _try_on_category(role)) is not None
        )
        all_references = tuple(image for _role, image in item_assets)
        await self._renders.mark_running(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
        )
        if not all_references:
            await self._degrade(artifact, fallback, "没有可试穿的服装单品。展示真实单品拼贴")
            return

        if self._audited_try_on_generator is not None:
            try:
                outfit_board = normalize_provider_image(self._collages.render(all_references))
                generated = await self._audited_try_on_generator.try_on(
                    model_image=model_image,
                    outfit_board=outfit_board,
                )
                trace = generated.provider_trace.with_parameters(
                    capability_id=TRY_ON_CAPABILITY_ID,
                    capability_alias="doubao_virtual_try_on_skill",
                    prompt_version=TRY_ON_PIPELINE_VERSION,
                    schema_version=TRY_ON_SCHEMA_VERSION,
                    garment_count=len(all_references),
                    personalization=(
                        "user_photo" if artifact.subject_object_key is not None else "fixed_model"
                    ),
                    strategy="analyze_generate_audit_retry",
                )
                await self._renders.mark_running(
                    user_id=artifact.user_id,
                    artifact_id=artifact.id,
                    provider_trace=trace,
                )
                await self._store_success(artifact, _generated_payload(generated))
                return
            except RenderProviderError as error:
                reason = (
                    str(error)
                    if error.code == "try_on_source_photo_ineligible"
                    else "真人试穿未通过身份、比例或服装保真审计，已保留真实单品拼贴。"  # noqa: RUF001
                )
                await self._degrade(artifact, fallback, reason)
                return
            except ValueError:
                await self._degrade(
                    artifact,
                    fallback,
                    "真人试穿未通过身份或服装保真审计。已保留真实单品拼贴",
                )
                return

        personalization = "user_photo" if artifact.subject_object_key is not None else "fixed_model"
        requires_complete_image_edit = (
            artifact.subject_object_key is not None
            or _fixed_model_requires_complete_image_edit(item_assets)
        )
        if requires_complete_image_edit and self._pixel_generator is not None:
            try:
                generated = await self._pixel_generator.generate(
                    prompt=TRY_ON_PROMPT,
                    images=(model_image, *all_references),
                    size=TRY_ON_OUTPUT_SIZE,
                )
                trace = generated.provider_trace.with_parameters(
                    capability_id=TRY_ON_CAPABILITY_ID,
                    capability_alias="image_generation",
                    prompt_version=TRY_ON_PROMPT_VERSION,
                    schema_version=TRY_ON_SCHEMA_VERSION,
                    garment_count=len(all_references),
                    personalization=personalization,
                    strategy="multimodal_image_edit",
                )
                await self._renders.mark_running(
                    user_id=artifact.user_id,
                    artifact_id=artifact.id,
                    provider_trace=trace,
                )
                await self._store_success(artifact, _generated_payload(generated))
                return
            except (RenderProviderError, ValueError):
                pass

        dedicated_covers_complete_look = len(dedicated_garments) == len(all_references)
        if (
            self._try_on_generator is not None
            and dedicated_garments
            and dedicated_covers_complete_look
        ):
            dedicated_result = await self._try_with_dedicated_provider(
                artifact=artifact,
                model_image=model_image,
                garments=dedicated_garments,
            )
            if dedicated_result is not None:
                return

        if dedicated_garments and not dedicated_covers_complete_look:
            await self._degrade(
                artifact,
                fallback,
                "专用试穿无法完整覆盖鞋履、配饰或其他单品。已保留整套真实单品拼贴",
            )
            return

        reason = (
            "真人试穿服务暂时不可用。已保留真实单品拼贴"
            if artifact.subject_object_key is not None
            else "固定模特预览暂时不可用。展示真实单品拼贴"
        )
        await self._degrade(artifact, fallback, reason)

    async def _try_with_dedicated_provider(
        self,
        *,
        artifact: RenderArtifact,
        model_image: ImagePayload,
        garments: tuple[tuple[str, ImagePayload], ...],
    ) -> GeneratedImage | None:
        if self._try_on_generator is None:
            return None
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
            return None
        if last_generated is None:
            return None
        trace = last_generated.provider_trace.with_parameters(
            capability_id=TRY_ON_CAPABILITY_ID,
            capability_alias="specialized_try_on",
            prompt_version="not_applicable",
            schema_version=TRY_ON_SCHEMA_VERSION,
            garment_count=len(garments),
            personalization=(
                "user_photo" if artifact.subject_object_key is not None else "fixed_model"
            ),
            strategy="virtual_try_on",
        )
        await self._renders.mark_running(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
            provider_trace=trace,
        )
        await self._store_success(artifact, _generated_payload(last_generated))
        return last_generated

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
        for component in ready[:8]:
            item = await self._wardrobe.get_for_user(
                component.item_id,  # type: ignore[arg-type]
                artifact.user_id,
            )
            if item is None:
                raise CollageRenderError("render Look references a missing Item")
            flat_lay = (
                await self._item_presentations.get_current_flat_lay_item(
                    user_id=artifact.user_id,
                    item_id=item.id,
                )
                if self._item_presentations is not None
                else None
            )
            if flat_lay is not None and flat_lay.status in {
                ItemPresentationStatus.QUEUED,
                ItemPresentationStatus.RUNNING,
            }:
                raise RetryableRenderError("generated Item flat-lay is not ready")
            object_key = (
                (
                    flat_lay.object_key
                    if flat_lay is not None
                    and flat_lay.status is ItemPresentationStatus.SUCCEEDED
                    and flat_lay.object_key is not None
                    else None
                )
                or item.display_object_key
                or (item.source_object_key if item.source_available else None)
            )
            if object_key is None:
                raise CollageRenderError("render Item has no available display image")
            assets.append(
                (component.role, normalize_provider_image(self._objects.read_image(object_key)))
            )
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
        allowed_source_kinds = {RenderArtifactKind.COLLAGE}
        if artifact.kind is RenderArtifactKind.PIXEL_COVER:
            allowed_source_kinds.add(RenderArtifactKind.TRY_ON)
        if fallback.kind not in allowed_source_kinds:
            return None
        if fallback.status is not RenderArtifactStatus.SUCCEEDED:
            return None
        return fallback

    async def _record_provider_and_store(
        self,
        artifact: RenderArtifact,
        generated: GeneratedImage,
        *,
        capability_id: str,
        prompt_version: str,
        schema_version: str,
        extra_parameters: dict[str, object] | None = None,
    ) -> None:
        await self._renders.mark_running(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
            provider_trace=generated.provider_trace.with_parameters(
                capability_id=capability_id,
                capability_alias="image_generation",
                prompt_version=prompt_version,
                schema_version=schema_version,
                **(extra_parameters or {}),
            ),
        )
        generated_payload = _generated_payload(generated)
        sprite: ImagePayload | None = None
        sprite_extraction_failed = False
        if (
            artifact.kind is RenderArtifactKind.PIXEL_COVER
            and self._pixel_sprite_extractor is not None
        ):
            try:
                sprite = self._pixel_sprite_extractor.extract(generated_payload)
            except PixelSpriteExtractionError:
                # The card remains useful in the wardrobe. Older and unusual cards
                # continue through the browser-side compatibility cutout until a
                # replacement sprite can be generated.
                sprite = None
                sprite_extraction_failed = True
        await self._store_success(
            artifact,
            generated_payload,
            sprite=sprite,
            sprite_extraction_failed=sprite_extraction_failed,
        )

    async def _backfill_pixel_sprite(self, artifact: RenderArtifact) -> None:
        if self._pixel_sprite_extractor is None or artifact.output is None:
            return
        try:
            card = self._objects.read_image(artifact.output.object_key)
            sprite = self._pixel_sprite_extractor.extract(card)
        except (FileNotFoundError, KeyError, OSError, PixelSpriteExtractionError):
            await self._renders.mark_sprite_extraction_failed(
                user_id=artifact.user_id,
                artifact_id=artifact.id,
            )
            return
        stored_sprite = self._objects.write_derived_image(
            sprite,
            owner_id=artifact.user_id,
            prefix="derived/render-sprites",
        )
        await self._renders.attach_sprite(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
            sprite_output=RenderOutput(
                object_key=stored_sprite.object_key,
                content_hash=stored_sprite.sha256,
                content_type=stored_sprite.content_type,
            ),
        )

    async def _store_success(
        self,
        artifact: RenderArtifact,
        image: ImagePayload,
        *,
        sprite: ImagePayload | None = None,
        sprite_extraction_failed: bool = False,
    ) -> None:
        stored = self._objects.write_derived_image(
            image,
            owner_id=artifact.user_id,
            prefix="derived/renders",
        )
        stored_sprite = (
            self._objects.write_derived_image(
                sprite,
                owner_id=artifact.user_id,
                prefix="derived/render-sprites",
            )
            if sprite is not None
            else None
        )
        await self._renders.mark_succeeded(
            user_id=artifact.user_id,
            artifact_id=artifact.id,
            output=RenderOutput(
                object_key=stored.object_key,
                content_hash=stored.sha256,
                content_type=stored.content_type,
            ),
            sprite_output=(
                RenderOutput(
                    object_key=stored_sprite.object_key,
                    content_hash=stored_sprite.sha256,
                    content_type=stored_sprite.content_type,
                )
                if stored_sprite is not None
                else None
            ),
            sprite_extraction_failed=sprite_extraction_failed,
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


def _fixed_model_requires_complete_image_edit(
    item_assets: tuple[tuple[str | None, ImagePayload], ...],
) -> bool:
    roles = {role for role, _image in item_assets if role is not None}
    return len(roles) > 1 or any(_try_on_category(role) is None for role, _image in item_assets)
