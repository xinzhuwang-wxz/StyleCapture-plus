from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.pixel_trial.application import PixelTrialApplication
from stylecapture_backend.features.pixel_trial.ports import PixelTrialNotFound
from stylecapture_backend.features.render.domain import RenderOutput
from stylecapture_backend.features.render.ports import GeneratedImage, RenderProviderError


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
    ) -> GeneratedImage: ...


PIXEL_TRIAL_PROMPT = """
把用户上传的正面全身照转换为可爱的像素风小人头像。
要求:
- 保留用户真实服装的主色、层次、轮廓和发型/体态特征;
- 生成完整站姿小人, 透明或浅色纯背景;
- 不添加品牌标识、文字、水印或额外人物;
- 输出应适合作为 StyleCapture 数字衣橱里的像素形象预览。
""".strip()
PIXEL_TRIAL_CAPABILITY_ID = "photo.pixel_trial"
PIXEL_TRIAL_PROMPT_VERSION = "photo-pixel-trial-zh-v1"
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
            subject = self._objects.read_image(trial.subject_object_key)
            generated = await self._generator.generate(
                prompt=PIXEL_TRIAL_PROMPT,
                images=(subject,),
                size="2K",
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
