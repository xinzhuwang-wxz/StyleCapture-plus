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

    async def generate(
        self,
        *,
        prompt: str,
        images: Sequence[ImagePayload],
        size: str = "1024x1024",
    ) -> GeneratedImage:
        assert "6-10px" in prompt
        assert "不默认使用粉色" in prompt
        assert len(images) == 1
        self.images = tuple(images)
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
    assert stored.provider_trace.parameters["prompt_version"] == "photo-pixel-trial-zh-v2"
    assert stored.provider_trace.parameters["schema_version"] == "generated-image-v1"


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
    assert "身份线索" in PIXEL_TRIAL_PROMPT
    assert "鞋履、配饰" in PIXEL_TRIAL_PROMPT
    assert "与原场景有关" in PIXEL_TRIAL_PROMPT
    assert "不复刻完整房间" in PIXEL_TRIAL_PROMPT


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
