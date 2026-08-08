from __future__ import annotations

# ruff: noqa: RUF001 -- Chinese prompt punctuation is intentional.
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.pixel_trial.application import PixelTrialApplication
from stylecapture_backend.features.pixel_trial.ports import PixelTrialNotFound
from stylecapture_backend.features.render.domain import RenderOutput
from stylecapture_backend.features.render.pixel_card_style import (
    PIXEL_CARD_GUIDANCE_SCALE,
    PIXEL_CARD_SEED,
    PIXEL_CARD_STYLE_REFERENCE_VERSION,
    build_pixel_card_prompt,
    load_pixel_card_style_references,
    pixel_card_style_reference_hashes,
)
from stylecapture_backend.features.render.ports import GeneratedImage, RenderProviderError
from stylecapture_backend.platform.image_normalization import normalize_provider_image


class RetryablePixelTrialError(RuntimeError):
    """The pixel trial can be retried safely by the worker."""


class PixelTrialObjectStore(Protocol):
    def read_image(self, object_key: str) -> ImagePayload: ...

    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload: ...


class PixelImageGenerator(Protocol):
    async def generate(
        self,
        *,
        prompt: str,
        images: Sequence[ImagePayload],
        size: str = "1024x1024",
        seed: int | None = None,
        guidance_scale: float | None = None,
    ) -> GeneratedImage: ...


PIXEL_TRIAL_OUTPUT_SIZE = "1728x2304"


PIXEL_TRIAL_PROMPT = build_pixel_card_prompt(
    "图1是人物内容图；最后两张图只提供画风、人物与脸部比例、粗像素颗粒、卡片留白和地毯结构。"
    "只从图1读取人物、服装与配饰，不继承示例卡片的背景配色或装饰主题。"
)
PIXEL_TRIAL_CAPABILITY_ID = "photo.pixel_trial"
PIXEL_TRIAL_PROMPT_VERSION = "photo-pixel-trial-zh-v5"
PIXEL_TRIAL_SCHEMA_VERSION = "generated-image-v1"


class PixelTrialProcessor:
    def __init__(
        self,
        *,
        trials: PixelTrialApplication,
        objects: PixelTrialObjectStore,
        generator: PixelImageGenerator,
    ) -> None:
        self._trials = trials
        self._objects = objects
        self._generator = generator

    async def process(
        self,
        *,
        user_id: UUID,
        trial_id: UUID,
        final_attempt: bool = False,
    ) -> None:
        try:
            trial = await self._trials.get(user_id=user_id, trial_id=trial_id)
        except PixelTrialNotFound:
            return
        if trial.status.value in {"succeeded", "failed"}:
            return
        if trial.subject_object_key is None:
            await self._trials.mark_failed(
                user_id=user_id,
                trial_id=trial_id,
                code="subject_missing",
                message="上传的全身照已删除, 无法生成像素形象",
            )
            return
        running = await self._trials.mark_running(user_id=user_id, trial_id=trial_id)
        try:
            subject = normalize_provider_image(self._objects.read_image(trial.subject_object_key))
            generated = await self._generator.generate(
                prompt=PIXEL_TRIAL_PROMPT,
                images=(subject, *load_pixel_card_style_references()),
                size=PIXEL_TRIAL_OUTPUT_SIZE,
                seed=PIXEL_CARD_SEED,
                guidance_scale=PIXEL_CARD_GUIDANCE_SCALE,
            )
            stored = self._objects.write_derived_image(
                ImagePayload(
                    object_key=f"derived/pixel-trials/{trial_id}",
                    content_type=generated.content_type,
                    body=generated.body,
                    sha256=generated.sha256,
                ),
                owner_id=user_id,
                prefix=f"derived/pixel-trials/{user_id}/{trial_id}",
            )
            await self._trials.mark_succeeded(
                user_id=user_id,
                trial_id=trial_id,
                output=RenderOutput(
                    object_key=stored.object_key,
                    content_hash=stored.sha256,
                    content_type=stored.content_type,
                ),
                provider_trace=generated.provider_trace.with_parameters(
                    capability_id=PIXEL_TRIAL_CAPABILITY_ID,
                    capability_alias="image_generation",
                    prompt_version=PIXEL_TRIAL_PROMPT_VERSION,
                    schema_version=PIXEL_TRIAL_SCHEMA_VERSION,
                    style_reference_version=PIXEL_CARD_STYLE_REFERENCE_VERSION,
                    style_reference_hashes=pixel_card_style_reference_hashes(),
                ),
            )
        except (FileNotFoundError, KeyError):
            await self._trials.mark_failed(
                user_id=user_id,
                trial_id=trial_id,
                code="subject_unavailable",
                message="上传的全身照暂时不可用, 请重新上传后再试",
            )
        except RenderProviderError as error:
            if error.retryable and running.status.value == "running" and not final_attempt:
                raise RetryablePixelTrialError(str(error)) from error
            await self._trials.mark_failed(
                user_id=user_id,
                trial_id=trial_id,
                code=error.code,
                message="像素形象暂时未生成, 请重新上传全身照再试",
            )
