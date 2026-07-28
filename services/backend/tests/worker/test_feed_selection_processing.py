from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    FeedFrameContext,
    FeedSelection,
    ImagePayload,
    JobState,
    NormalizedPoint,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.feed_media import (
    SegmentationMetadata,
    SegmentationPrompt,
    SegmentationRepresentation,
    SegmentationResult,
)
from stylecapture_backend.features.capture.processing import (
    CaptureProcessor,
    EmbeddingResult,
    ModelMetadata,
    ProcessingOutcome,
    ProviderError,
    VisionAnalysis,
)
from stylecapture_backend.features.wardrobe.domain import (
    ItemStatus,
    ModelField,
    WardrobeItem,
)


class MemoryWorkRepository:
    def __init__(self, capture: Capture, job: ProcessingJob) -> None:
        self.capture = capture
        self.job = job

    async def get_capture(self, capture_id: UUID) -> Capture | None:
        return self.capture if capture_id == self.capture.id else None

    async def get_job(self, job_id: UUID) -> ProcessingJob | None:
        return self.job if job_id == self.job.id else None

    async def update(self, job: ProcessingJob) -> ProcessingJob:
        self.job = job
        return job


class MemoryWardrobeRepository:
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, str], WardrobeItem] = {}

    async def get_by_capture(
        self,
        capture_id: UUID,
        selection_key: str = "whole_capture",
    ) -> WardrobeItem | None:
        return self.items.get((capture_id, selection_key))

    async def save(self, item: WardrobeItem) -> WardrobeItem:
        identity = (item.capture_id, item.selection_key)
        current = self.items.get(identity)
        if current is not None and current.id != item.id:
            raise AssertionError("processor attempted to replace a stable selection Item")
        self.items[identity] = item
        return item


@dataclass(frozen=True)
class MemoryObjects:
    payload: ImagePayload
    derived: dict[str, ImagePayload] | None = None

    def read_image(self, object_key: str) -> ImagePayload:
        if object_key != self.payload.object_key:
            raise KeyError(object_key)
        return self.payload

    async def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload:
        del owner_id
        if self.derived is None:
            object.__setattr__(self, "derived", {})
        derived = self.derived
        assert derived is not None
        extension = ".png" if image.content_type == "image/png" else ".bin"
        stored = ImagePayload(
            object_key=f"{prefix.rstrip('/')}/{image.sha256}{extension}",
            content_type=image.content_type,
            body=image.body,
            sha256=image.sha256,
        )
        derived[stored.object_key] = stored
        return stored


class RecordingSegmenter:
    def __init__(self) -> None:
        self.prompts: list[SegmentationPrompt] = []

    def segment(self, prompt: SegmentationPrompt) -> SegmentationResult:
        self.prompts.append(prompt)
        return SegmentationResult(
            selection_key=prompt.selection.selection_key,
            coarse_polygon=prompt.selection.polygon,
            mask=None,
            metadata=SegmentationMetadata(
                capability_alias="deterministic_lasso_fallback",
                representation=SegmentationRepresentation.COARSE_POLYGON,
                refined=False,
                schema_version="feed-segmentation-v1",
                latency_ms=0,
                fallback_reason=prompt.fallback_reason,
            ),
        )


class SelectionImages:
    def render(
        self,
        frame: ImagePayload,
        segmentation: SegmentationResult,
    ) -> ImagePayload:
        return ImagePayload(
            object_key=f"{frame.object_key}#selection={segmentation.selection_key}",
            content_type="image/png",
            body=f"pixels:{segmentation.selection_key}".encode(),
            sha256="f" * 64,
        )


class RecordingVision:
    def __init__(self, error: ProviderError | None = None) -> None:
        self.error = error
        self.calls: list[tuple[ImagePayload, FeedSelection | None]] = []

    async def describe(
        self,
        image: ImagePayload,
        *,
        selection: FeedSelection | None = None,
    ) -> VisionAnalysis:
        self.calls.append((image, selection))
        if self.error is not None:
            raise self.error
        assert selection is not None
        return VisionAnalysis(
            fields={
                "category": ModelField(
                    value=f"category-for-{selection.selection_key}",
                    confidence=0.91,
                    model_version="provider-model-v1",
                )
            },
            metadata=ModelMetadata(
                capability_alias="vision_understanding",
                provider_model="provider-model-v1",
                prompt_version="garment-v1",
                schema_version="garment-v1",
                taxonomy_version="stylecapture-v1",
                latency_ms=12,
            ),
        )


class FixedEmbedder:
    async def embed(self, image: ImagePayload) -> EmbeddingResult:
        return EmbeddingResult(
            vector=(1.0,) + (0.0,) * 2047,
            model_version="doubao-embedding-vision-250615",
        )


def feed_capture_job() -> tuple[Capture, ProcessingJob]:
    polygon = (
        NormalizedPoint(0.1, 0.1),
        NormalizedPoint(0.4, 0.1),
        NormalizedPoint(0.4, 0.5),
        NormalizedPoint(0.1, 0.5),
    )
    capture = Capture.create(
        user_id=uuid4(),
        source=CaptureSource(
            kind=CaptureSourceKind.FEED,
            object_key="originals/feed/frame.png",
            sha256="a" * 64,
            origin_ref="pexels-123",
        ),
        ownership=OwnershipState.INSPIRATION,
        feed_context=FeedFrameContext(
            video_ref="pexels-123",
            timestamp_ms=1_200,
            frame_width=720,
            frame_height=1280,
            selections=(
                FeedSelection(selection_key="hat", polygon=polygon),
                FeedSelection(selection_key="jacket", polygon=polygon),
            ),
        ),
    )
    return capture, ProcessingJob.queued(capture_id=capture.id)


def image_for(capture: Capture) -> ImagePayload:
    return ImagePayload(
        object_key=capture.source.object_key,
        content_type="image/png",
        body=b"real-feed-frame",
        sha256=capture.source.sha256,
    )


def build_processor(
    capture: Capture,
    job: ProcessingJob,
    *,
    vision: RecordingVision,
) -> tuple[
    CaptureProcessor,
    MemoryWorkRepository,
    MemoryWardrobeRepository,
    RecordingSegmenter,
]:
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    segmenter = RecordingSegmenter()
    objects = MemoryObjects(image_for(capture))
    return (
        CaptureProcessor(
            captures=work,
            jobs=work,
            wardrobe=wardrobe,
            objects=objects,
            vision=vision,
            embedder=FixedEmbedder(),
            segmenter=segmenter,
            selection_images=SelectionImages(),
            display_assets=objects,
        ),
        work,
        wardrobe,
        segmenter,
    )


@pytest.mark.asyncio
async def test_feed_batch_creates_one_item_per_selection_with_prompt_boundaries() -> None:
    capture, job = feed_capture_job()
    vision = RecordingVision()
    processor, work, wardrobe, segmenter = build_processor(
        capture,
        job,
        vision=vision,
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome == ProcessingOutcome.ready()
    assert work.job.state is JobState.READY
    assert set(wardrobe.items) == {
        (capture.id, "hat"),
        (capture.id, "jacket"),
    }
    assert [prompt.selection.selection_key for prompt in segmenter.prompts] == [
        "hat",
        "jacket",
    ]
    assert [selection.selection_key for _, selection in vision.calls if selection] == [
        "hat",
        "jacket",
    ]
    assert [image.object_key for image, _ in vision.calls] == [
        "originals/feed/frame.png#selection=hat",
        "originals/feed/frame.png#selection=jacket",
    ]
    for selection in capture.feed_context.selections if capture.feed_context else ():
        item = wardrobe.items[(capture.id, selection.selection_key)]
        assert item.status is ItemStatus.READY
        assert item.selection_key == selection.selection_key
        assert item.attributes.fields["category"].value == f"category-for-{selection.selection_key}"
        segmentation = item.model_metadata["segmentation"]
        assert isinstance(segmentation, dict)
        assert segmentation["selection_key"] == selection.selection_key
        assert segmentation["coarse_polygon"] == [
            {"x": point.x, "y": point.y} for point in selection.polygon
        ]


@pytest.mark.asyncio
async def test_feed_selection_persists_display_asset_separately_from_source_evidence() -> None:
    capture, job = feed_capture_job()
    vision = RecordingVision()
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    segmenter = RecordingSegmenter()
    objects = MemoryObjects(image_for(capture))
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=objects,
        vision=vision,
        embedder=FixedEmbedder(),
        segmenter=segmenter,
        selection_images=SelectionImages(),
        display_assets=objects,
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome == ProcessingOutcome.ready()
    assert objects.derived is not None
    assert set(objects.derived) == {
        "derived/items/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff.png"
    }
    for selection in capture.feed_context.selections if capture.feed_context else ():
        item = wardrobe.items[(capture.id, selection.selection_key)]
        assert item.source_object_key == capture.source.object_key
        assert item.display_object_key == (
            "derived/items/ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff.png"
        )


@pytest.mark.asyncio
async def test_feed_batch_retry_reuses_stable_selection_items() -> None:
    capture, job = feed_capture_job()
    first_vision = RecordingVision(
        error=ProviderError(
            "vision_unavailable",
            "Vision is temporarily unavailable",
            retryable=True,
        )
    )
    processor, work, wardrobe, _ = build_processor(
        capture,
        job,
        vision=first_vision,
    )

    first_outcome = await processor.process(capture.id, job.id)
    original_ids = {selection_key: item.id for (_, selection_key), item in wardrobe.items.items()}

    first_vision.error = None
    second_outcome = await processor.process(capture.id, job.id)

    assert first_outcome.state is JobState.PARTIAL
    assert first_outcome.retryable is True
    assert second_outcome == ProcessingOutcome.ready()
    assert work.job.state is JobState.READY
    assert {
        selection_key: item.id for (_, selection_key), item in wardrobe.items.items()
    } == original_ids
    assert len(wardrobe.items) == 2
    assert all(
        item.model_metadata.get("processing_error") is None for item in wardrobe.items.values()
    )


@pytest.mark.asyncio
async def test_feed_without_vlm_keeps_real_selection_items_partial_without_tags() -> None:
    capture, job = feed_capture_job()
    processor, work, wardrobe, _ = build_processor(
        capture,
        job,
        vision=RecordingVision(
            error=ProviderError(
                "vision_unavailable",
                "Vision is temporarily unavailable",
                retryable=True,
            )
        ),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.PARTIAL
    assert outcome.retryable is True
    assert outcome.error_code == "vision_unavailable"
    assert work.job.state is JobState.PARTIAL
    assert len(wardrobe.items) == 2
    for item in wardrobe.items.values():
        assert item.status is ItemStatus.PARTIAL
        assert not item.attributes.fields
        segmentation = item.model_metadata["segmentation"]
        assert isinstance(segmentation, dict)
        assert segmentation["representation"] == "coarse_polygon"


@pytest.mark.asyncio
async def test_feed_without_refinement_adapter_keeps_each_selection_retryable() -> None:
    capture, job = feed_capture_job()
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    vision = RecordingVision()
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MemoryObjects(image_for(capture)),
        vision=vision,
        embedder=FixedEmbedder(),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.PARTIAL
    assert outcome.retryable is True
    assert outcome.error_code == "feed_selection_processing_unavailable"
    assert not vision.calls
    assert set(wardrobe.items) == {
        (capture.id, "hat"),
        (capture.id, "jacket"),
    }
    assert all(
        item.status is ItemStatus.PARTIAL and not item.attributes.fields
        for item in wardrobe.items.values()
    )
