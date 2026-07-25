from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    FeedSelection,
    JobState,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.processing import (
    CaptureProcessor,
    EmbeddingResult,
    ImagePayload,
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

    async def describe(
        self,
        image: ImagePayload,
        *,
        selection: FeedSelection | None = None,
    ) -> VisionAnalysis:
        self.calls += 1
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

    async def embed(self, image: ImagePayload) -> EmbeddingResult:
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


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
    assert wardrobe.item is not None
    assert wardrobe.item.status is ItemStatus.ERROR


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
