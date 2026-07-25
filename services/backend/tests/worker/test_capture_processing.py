from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    FeedSelection,
    ImagePayload,
    JobState,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.feed_media import (
    SegmentationMetadata,
    SegmentationPrompt,
    SegmentationRepresentation,
    SegmentationResult,
)
from stylecapture_backend.features.capture.grounding import (
    GroundingAnalysis,
    GroundingCandidate,
    NormalizedBox,
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
    FieldEnvelope,
    FieldProvenance,
    ItemAttributes,
    ItemStatus,
    ModelField,
    WardrobeItem,
)
from stylecapture_backend.features.wardrobe.taxonomy import GarmentCategory


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
    def __init__(self, item: WardrobeItem | None = None) -> None:
        self.item = item

    async def get_by_capture(
        self,
        capture_id: UUID,
        selection_key: str = "whole_capture",
    ) -> WardrobeItem | None:
        if (
            self.item is None
            or self.item.capture_id != capture_id
            or self.item.selection_key != selection_key
        ):
            return None
        return self.item

    async def save(self, item: WardrobeItem) -> WardrobeItem:
        self.item = item
        return item


@dataclass(frozen=True)
class MemoryObjects:
    payload: ImagePayload

    def read_image(self, object_key: str) -> ImagePayload:
        if object_key != self.payload.object_key:
            raise KeyError(object_key)
        return self.payload


class MissingObjects:
    def read_image(self, object_key: str) -> ImagePayload:
        raise FileNotFoundError(object_key)


class FixedVision:
    def __init__(
        self,
        result: VisionAnalysis | None = None,
        error: ProviderError | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0
        self.images: list[ImagePayload] = []

    async def describe(
        self,
        image: ImagePayload,
        *,
        selection: FeedSelection | None = None,
    ) -> VisionAnalysis:
        self.calls += 1
        self.images.append(image)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class FixedEmbedder:
    def __init__(
        self,
        result: EmbeddingResult | None = None,
        error: ProviderError | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.images: list[ImagePayload] = []

    async def embed(self, image: ImagePayload) -> EmbeddingResult:
        self.images.append(image)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class RecordingGrounder:
    def __init__(
        self,
        candidates: tuple[GroundingCandidate, ...],
        error: ProviderError | None = None,
    ) -> None:
        self.candidates = candidates
        self.error = error
        self.calls: list[FeedSelection] = []

    async def ground(self, image: ImagePayload, *, scope: FeedSelection) -> GroundingAnalysis:
        del image
        self.calls.append(scope)
        if self.error is not None:
            raise self.error
        return GroundingAnalysis(
            candidates=self.candidates,
            metadata=ModelMetadata(
                capability_alias="visual_grounding",
                provider_model="internal-provider-id",
                prompt_version="grounding-v1",
                schema_version="ark-bbox-tags-v1",
                taxonomy_version="stylecapture-v1",
                latency_ms=8,
            ),
        )


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
                capability_alias="sam2_hiera_tiny",
                representation=SegmentationRepresentation.COARSE_POLYGON,
                refined=False,
                schema_version="feed-segmentation-v1",
                latency_ms=6,
                fallback_reason=prompt.fallback_reason,
            ),
        )


class SelectionImages:
    selected = ImagePayload(
        object_key="derived/transient/single-garment.png",
        content_type="image/png",
        body=b"transparent-garment-pixels",
        sha256="b" * 64,
    )

    def render(self, frame: ImagePayload, segmentation: SegmentationResult) -> ImagePayload:
        del frame, segmentation
        return self.selected


class MemoryDerivedImages:
    def __init__(self) -> None:
        self.images: dict[str, ImagePayload] = {}

    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload:
        del owner_id
        stored = ImagePayload(
            object_key=f"{prefix}/{image.sha256}.png",
            content_type=image.content_type,
            body=image.body,
            sha256=image.sha256,
        )
        self.images[stored.object_key] = stored
        return stored


def make_capture_job() -> tuple[Capture, ProcessingJob]:
    capture = Capture.create(
        user_id=uuid4(),
        source=CaptureSource(
            kind=CaptureSourceKind.CAMERA,
            object_key="originals/2026/07/25/garment.png",
            sha256="a" * 64,
        ),
        ownership=OwnershipState.OWNED,
    )
    return capture, ProcessingJob.queued(capture_id=capture.id)


def image_for(capture: Capture) -> ImagePayload:
    return ImagePayload(
        object_key=capture.source.object_key,
        content_type="image/png",
        body=b"real-image-bytes",
        sha256=capture.source.sha256,
    )


def analysis(fields: Mapping[str, ModelField] | None = None) -> VisionAnalysis:
    return VisionAnalysis(
        fields=fields
        or {
            "category": ModelField("tops", 0.98, "provider-model-v1"),
            "subcategory": ModelField("shirt", 0.95, "provider-model-v1"),
            "description": ModelField("一件蓝色宽松衬衫", 0.91, "provider-model-v1"),
            "colors": ModelField(["blue"], 0.96, "provider-model-v1"),
        },
        metadata=ModelMetadata(
            capability_alias="vision_understanding",
            provider_model="provider-model-v1",
            prompt_version="garment-v1",
            schema_version="garment-v1",
            taxonomy_version="stylecapture-v1",
            latency_ms=120,
        ),
    )


def embedding() -> EmbeddingResult:
    return EmbeddingResult(
        vector=(1.0,) + (0.0,) * 2047,
        model_version="doubao-embedding-vision-250615",
    )


def garment_candidate(
    label: str = "blue_shirt",
    *,
    category: GarmentCategory = GarmentCategory.TOPS,
    box: NormalizedBox | None = None,
    confidence: float = 0.96,
    visible_fraction: float = 0.92,
) -> GroundingCandidate:
    return GroundingCandidate(
        label=label,
        category=category,
        box=box or NormalizedBox(120, 90, 880, 930),
        confidence=confidence,
        visible_fraction=visible_fraction,
    )


@pytest.mark.asyncio
async def test_real_processing_contract_persists_ready_item_and_embedding() -> None:
    capture, job = make_capture_job()
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MemoryObjects(image_for(capture)),
        vision=FixedVision(result=analysis()),
        embedder=FixedEmbedder(result=embedding()),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome == ProcessingOutcome.ready()
    assert work.job.state is JobState.READY
    assert wardrobe.item is not None
    assert wardrobe.item.status is ItemStatus.READY
    assert wardrobe.item.embedding == embedding().vector
    assert wardrobe.item.attributes.fields["category"].value == "tops"
    assert wardrobe.item.model_metadata["capability_alias"] == "vision_understanding"


@pytest.mark.asyncio
async def test_upload_cache_miss_generates_transparent_display_before_tagging() -> None:
    capture, job = make_capture_job()
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    vision = FixedVision(result=analysis())
    embedder = FixedEmbedder(result=embedding())
    grounder = RecordingGrounder((garment_candidate(),))
    segmenter = RecordingSegmenter()
    display_assets = MemoryDerivedImages()
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MemoryObjects(image_for(capture)),
        vision=vision,
        embedder=embedder,
        grounder=grounder,
        segmenter=segmenter,
        selection_images=SelectionImages(),
        display_assets=display_assets,
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome == ProcessingOutcome.ready()
    assert wardrobe.item is not None
    assert wardrobe.item.source_object_key == capture.source.object_key
    assert wardrobe.item.display_object_key == (
        f"derived/items/{SelectionImages.selected.sha256}.png"
    )
    assert vision.images == [SelectionImages.selected]
    assert embedder.images == [SelectionImages.selected]
    assert len(grounder.calls) == 1
    assert len(segmenter.prompts) == 1
    normalization = wardrobe.item.model_metadata["normalization"]
    assert isinstance(normalization, Mapping)
    assert normalization["status"] == "succeeded"
    assert normalization["source"] == "runtime_extraction"
    assert display_assets.images[wardrobe.item.display_object_key].body == (
        b"transparent-garment-pixels"
    )


@pytest.mark.asyncio
async def test_upload_with_multiple_garments_is_rejected_without_tagging_or_embedding() -> None:
    capture, job = make_capture_job()
    original = image_for(capture)
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    vision = FixedVision(result=analysis())
    embedder = FixedEmbedder(result=embedding())
    grounder = RecordingGrounder(
        (
            garment_candidate("blue_shirt"),
            garment_candidate(
                "black_trousers",
                category=GarmentCategory.BOTTOMS,
                box=NormalizedBox(160, 480, 840, 970),
            ),
        )
    )
    segmenter = RecordingSegmenter()
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MemoryObjects(original),
        vision=vision,
        embedder=embedder,
        grounder=grounder,
        segmenter=segmenter,
        selection_images=SelectionImages(),
        display_assets=MemoryDerivedImages(),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.ERROR
    assert outcome.error_code == "multiple_garments"
    assert work.job.state is JobState.ERROR
    assert work.job.error_code == "multiple_garments"
    assert wardrobe.item is None
    assert vision.images == []
    assert embedder.images == []
    assert segmenter.prompts == []


@pytest.mark.asyncio
async def test_upload_without_reliable_garment_is_rejected_without_tagging_or_embedding() -> None:
    capture, job = make_capture_job()
    original = image_for(capture)
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    vision = FixedVision(result=analysis())
    embedder = FixedEmbedder(result=embedding())
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MemoryObjects(original),
        vision=vision,
        embedder=embedder,
        grounder=RecordingGrounder(
            (
                garment_candidate(
                    "unreliable_hint",
                    box=NormalizedBox(120, 90, 880, 930),
                    confidence=0.32,
                ),
            )
        ),
        segmenter=RecordingSegmenter(),
        selection_images=SelectionImages(),
        display_assets=MemoryDerivedImages(),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.ERROR
    assert outcome.error_code == "no_reliable_garment"
    assert work.job.state is JobState.ERROR
    assert wardrobe.item is None
    assert vision.images == []
    assert embedder.images == []


@pytest.mark.asyncio
async def test_upload_rejection_marks_existing_retry_item_error_without_creating_tags() -> None:
    capture, job = make_capture_job()
    original = image_for(capture)
    existing = WardrobeItem.processing(capture)
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository(existing)
    vision = FixedVision(result=analysis())
    embedder = FixedEmbedder(result=embedding())
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MemoryObjects(original),
        vision=vision,
        embedder=embedder,
        grounder=RecordingGrounder(
            (
                garment_candidate(
                    "unreliable_hint",
                    box=NormalizedBox(120, 90, 880, 930),
                    confidence=0.28,
                ),
            )
        ),
        segmenter=RecordingSegmenter(),
        selection_images=SelectionImages(),
        display_assets=MemoryDerivedImages(),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.ERROR
    assert outcome.error_code == "no_reliable_garment"
    assert wardrobe.item is not None
    assert wardrobe.item.id == existing.id
    assert wardrobe.item.status is ItemStatus.ERROR
    assert wardrobe.item.attributes.fields == {}
    assert wardrobe.item.display_object_key is None
    assert vision.images == []
    assert embedder.images == []
    assert wardrobe.item.model_metadata["normalization"] == {
        "status": "not_applied",
        "reason": "no_reliable_garment",
        "candidate_count": 0,
    }


@pytest.mark.asyncio
async def test_upload_grounding_failure_keeps_original_and_records_honest_fallback() -> None:
    capture, job = make_capture_job()
    original = image_for(capture)
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    vision = FixedVision(result=analysis())
    embedder = FixedEmbedder(result=embedding())
    grounder = RecordingGrounder(
        (garment_candidate(),),
        error=ProviderError(
            "grounding_unavailable",
            "grounding is temporarily unavailable",
            retryable=True,
        ),
    )
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MemoryObjects(original),
        vision=vision,
        embedder=embedder,
        grounder=grounder,
        segmenter=RecordingSegmenter(),
        selection_images=SelectionImages(),
        display_assets=MemoryDerivedImages(),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome == ProcessingOutcome.ready()
    assert wardrobe.item is not None
    assert wardrobe.item.display_object_key is None
    assert vision.images == [original]
    assert embedder.images == [original]
    assert wardrobe.item.model_metadata["normalization"] == {
        "status": "fallback",
        "reason": "grounding_unavailable",
        "retryable": True,
    }


@pytest.mark.asyncio
async def test_embedding_failure_keeps_real_tags_and_marks_partial_for_retry() -> None:
    capture, job = make_capture_job()
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MemoryObjects(image_for(capture)),
        vision=FixedVision(result=analysis()),
        embedder=FixedEmbedder(
            error=ProviderError(
                "embedding_unavailable",
                "embedding service is unavailable",
                retryable=True,
            )
        ),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.PARTIAL
    assert outcome.retryable is True
    assert work.job.state is JobState.PARTIAL
    assert work.job.error_code == "embedding_unavailable"
    assert wardrobe.item is not None
    assert wardrobe.item.status is ItemStatus.PARTIAL
    assert wardrobe.item.attributes.fields["category"].value == "tops"
    assert wardrobe.item.embedding is None


@pytest.mark.asyncio
async def test_vision_failure_retains_capture_and_marks_item_error() -> None:
    capture, job = make_capture_job()
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MemoryObjects(image_for(capture)),
        vision=FixedVision(
            error=ProviderError(
                "vision_unavailable",
                "vision service is unavailable",
                retryable=True,
            )
        ),
        embedder=FixedEmbedder(result=embedding()),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.ERROR
    assert outcome.retryable is True
    assert work.capture == capture
    assert work.job.error_code == "vision_unavailable"
    assert wardrobe.item is not None
    assert wardrobe.item.status is ItemStatus.ERROR


@pytest.mark.asyncio
async def test_deleted_source_reaches_stable_non_retryable_error() -> None:
    capture, job = make_capture_job()
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MissingObjects(),
        vision=FixedVision(result=analysis()),
        embedder=FixedEmbedder(result=embedding()),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.ERROR
    assert outcome.retryable is False
    assert outcome.error_code == "source_unavailable"
    assert work.job.state is JobState.ERROR
    assert work.job.error_code == "source_unavailable"
    assert wardrobe.item is None


@pytest.mark.asyncio
async def test_retry_never_overwrites_a_user_locked_field() -> None:
    capture, job = make_capture_job()
    failed_job = job.transition(JobState.PROCESSING).transition(
        JobState.ERROR,
        error_code="vision_unavailable",
        error_message="temporary failure",
    )
    locked_item = WardrobeItem.processing(capture).with_attributes(
        ItemAttributes(
            {
                "category": FieldEnvelope(
                    value="outerwear",
                    provenance=FieldProvenance.USER,
                    confidence=1,
                    model_version=None,
                    locked=True,
                )
            }
        )
    )
    work = MemoryWorkRepository(capture, failed_job)
    wardrobe = MemoryWardrobeRepository(locked_item)
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=MemoryObjects(image_for(capture)),
        vision=FixedVision(result=analysis()),
        embedder=FixedEmbedder(result=embedding()),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.READY
    assert work.job.attempt == 2
    assert wardrobe.item is not None
    assert wardrobe.item.attributes.fields["category"].value == "outerwear"
    assert wardrobe.item.attributes.fields["category"].provenance is FieldProvenance.USER
