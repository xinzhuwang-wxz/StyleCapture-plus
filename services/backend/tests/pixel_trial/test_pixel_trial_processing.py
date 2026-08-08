from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from PIL import Image
from pillow_heif import from_pillow
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.pixel_trial.application import PixelTrialApplication
from stylecapture_backend.features.pixel_trial.domain import PixelTrial, PixelTrialStatus
from stylecapture_backend.features.pixel_trial.processing import (
    PIXEL_CARD_GUIDANCE_SCALE,
    PIXEL_CARD_SEED,
    PIXEL_TRIAL_PROMPT,
    PixelTrialProcessor,
)
from stylecapture_backend.features.render.domain import RenderProviderTrace
from stylecapture_backend.features.render.ports import GeneratedImage


class MemoryTrials:
    def __init__(self, trial: PixelTrial) -> None:
        self.trials = {trial.id: trial}

    async def ensure_requested(self, trial: PixelTrial) -> PixelTrial:
        self.trials.setdefault(trial.id, trial)
        return self.trials[trial.id]

    async def save(self, trial: PixelTrial) -> PixelTrial:
        self.trials[trial.id] = trial
        return trial

    async def get_for_user(self, *, user_id: UUID, trial_id: UUID) -> PixelTrial | None:
        trial = self.trials.get(trial_id)
        return trial if trial is not None and trial.user_id == user_id else None

    async def delete_for_user(self, *, user_id: UUID, trial_id: UUID) -> PixelTrial | None:
        return await self.get_for_user(user_id=user_id, trial_id=trial_id)


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
        self.prompt = ""
        self.size = ""
        self.seed: int | None = None
        self.guidance_scale: float | None = None

    async def generate(
        self,
        *,
        prompt: str,
        images: Sequence[ImagePayload],
        size: str = "1024x1024",
        seed: int | None = None,
        guidance_scale: float | None = None,
    ) -> GeneratedImage:
        assert "图1是人物内容图" in prompt
        assert "最后两张图只提供画风" in prompt
        assert len(images) == 3
        self.prompt = prompt
        self.images = tuple(images)
        self.size = size
        self.seed = seed
        self.guidance_scale = guidance_scale
        body = b"real-provider-pixel-output"
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
async def test_pixel_trial_records_capability_prompt_and_schema_versions() -> None:
    user_id = uuid4()
    body = b"private-full-body-photo"
    source = ImagePayload(
        object_key="originals/upload/full-body.png",
        content_type="image/png",
        body=body,
        sha256=sha256(body).hexdigest(),
    )
    trial = PixelTrial.queued(
        user_id=user_id,
        subject_object_key=source.object_key,
        request_key="pixel-trial-processing",
    )
    repository = MemoryTrials(trial)
    generator = SuccessfulGenerator()
    processor = PixelTrialProcessor(
        trials=PixelTrialApplication(trials=repository),
        objects=MemoryObjects(source),
        generator=generator,
    )

    await processor.process(user_id=user_id, trial_id=trial.id)

    stored = repository.trials[trial.id]
    assert stored.status is PixelTrialStatus.SUCCEEDED
    assert stored.provider_trace is not None
    assert stored.provider_trace.parameters["capability_id"] == "photo.pixel_trial"
    assert stored.provider_trace.parameters["capability_alias"] == "image_generation"
    assert stored.provider_trace.parameters["prompt_version"] == "photo-pixel-trial-zh-v8-candidate"
    assert stored.provider_trace.parameters["schema_version"] == "generated-image-v1"
    assert (
        stored.provider_trace.parameters["style_reference_version"]
        == "pixel-card-style-v2-candidate"
    )
    assert generator.size == "1728x2304"
    assert generator.seed == PIXEL_CARD_SEED
    assert PIXEL_CARD_GUIDANCE_SCALE is None
    assert generator.guidance_scale is None
    assert "3:4" in generator.prompt
    assert generator.images[1].object_key.endswith("anchor-formal-light-pixel.png")
    assert generator.images[2].object_key.endswith("anchor-casual-dark-pixel.png")


@pytest.mark.asyncio
async def test_pixel_trial_converts_heic_subject_before_render_provider() -> None:
    user_id = uuid4()
    source = _heic_payload("originals/upload/full-body.heic")
    trial = PixelTrial.queued(
        user_id=user_id,
        subject_object_key=source.object_key,
        request_key="pixel-trial-heic",
    )
    repository = MemoryTrials(trial)
    generator = SuccessfulGenerator()
    processor = PixelTrialProcessor(
        trials=PixelTrialApplication(trials=repository),
        objects=MemoryObjects(source),
        generator=generator,
    )

    await processor.process(user_id=user_id, trial_id=trial.id)

    assert repository.trials[trial.id].status is PixelTrialStatus.SUCCEEDED
    assert generator.images[0].content_type == "image/jpeg"
    assert generator.images[0].object_key.endswith(".render-input.jpg")


def test_pixel_trial_prompt_preserves_the_subject_without_fixed_decoration() -> None:
    assert "3:4" in PIXEL_TRIAL_PROMPT
    assert "由穿搭主辅色、配饰和气质延伸" in PIXEL_TRIAL_PROMPT
    assert "避免大面积纯白或中性灰" in PIXEL_TRIAL_PROMPT
    assert "图标从原场景语义抽象" in PIXEL_TRIAL_PROMPT
    assert "不画完整场景" in PIXEL_TRIAL_PROMPT
    assert "不继承示例卡片的背景配色或装饰主题" in PIXEL_TRIAL_PROMPT
    assert "头顶、手臂和鞋底" in PIXEL_TRIAL_PROMPT
    assert "姿势属于人物内容" in PIXEL_TRIAL_PROMPT
    assert "伸展动作通过缩小人物完整容纳" in PIXEL_TRIAL_PROMPT
    assert "不改成对称立正" in PIXEL_TRIAL_PROMPT
    assert "眼睛较大圆润有高光" in PIXEL_TRIAL_PROMPT
    assert "避免小眼睛、长中庭和低幼娃娃" in PIXEL_TRIAL_PROMPT
    assert "鼻子只用" not in PIXEL_TRIAL_PROMPT
    assert "单个不超过人物头宽四分之一" in PIXEL_TRIAL_PROMPT
    assert "用明暗层级概括发丝、衣褶和材质" in PIXEL_TRIAL_PROMPT
    assert len(PIXEL_TRIAL_PROMPT) < 650


def _heic_payload(object_key: str) -> ImagePayload:
    image = Image.new("RGB", (8, 6), (65, 110, 190))
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
