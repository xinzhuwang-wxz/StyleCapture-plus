from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isclose, sqrt
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSourceKind,
    FeedSelection,
    ImagePayload,
    JobState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.feed_media import (
    PromptableSegmentationPort,
    SegmentationPrompt,
    SegmentationResult,
    SelectionImageRenderer,
)
from stylecapture_backend.features.wardrobe.domain import (
    WHOLE_CAPTURE_SELECTION_KEY,
    ItemStatus,
    ModelField,
    WardrobeItem,
)


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    capability_alias: str
    provider_model: str
    prompt_version: str
    schema_version: str
    taxonomy_version: str
    latency_ms: int

    def as_dict(self) -> dict[str, object]:
        return {
            "capability_alias": self.capability_alias,
            "provider_model": self.provider_model,
            "prompt_version": self.prompt_version,
            "schema_version": self.schema_version,
            "taxonomy_version": self.taxonomy_version,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True, slots=True)
class VisionAnalysis:
    fields: Mapping[str, ModelField]
    metadata: ModelMetadata

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", dict(self.fields))
        if not self.fields:
            raise ValueError("vision analysis must contain fields")


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vector: tuple[float, ...]
    model_version: str

    def __post_init__(self) -> None:
        if not self.vector:
            raise ValueError("embedding must not be empty")
        norm = sqrt(sum(value * value for value in self.vector))
        if not isclose(norm, 1, rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError("embedding must be L2-normalized")
        if not self.model_version.strip():
            raise ValueError("embedding model version must not be empty")


class ProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ProcessingOutcome:
    state: JobState
    retryable: bool
    error_code: str | None = None

    @classmethod
    def ready(cls) -> ProcessingOutcome:
        return cls(state=JobState.READY, retryable=False)

    @classmethod
    def partial(cls, error: ProviderError) -> ProcessingOutcome:
        return cls(
            state=JobState.PARTIAL,
            retryable=error.retryable,
            error_code=error.code,
        )

    @classmethod
    def error(cls, error: ProviderError) -> ProcessingOutcome:
        return cls(
            state=JobState.ERROR,
            retryable=error.retryable,
            error_code=error.code,
        )


class CaptureWorkReader(Protocol):
    async def get_capture(self, capture_id: UUID) -> Capture | None: ...


class WorkJobRepository(Protocol):
    async def get_job(self, job_id: UUID) -> ProcessingJob | None: ...

    async def update(self, job: ProcessingJob) -> ProcessingJob: ...


class WardrobeWriter(Protocol):
    async def get_by_capture(
        self,
        capture_id: UUID,
        selection_key: str = WHOLE_CAPTURE_SELECTION_KEY,
    ) -> WardrobeItem | None: ...

    async def save(self, item: WardrobeItem) -> WardrobeItem: ...


class ImageReader(Protocol):
    def read_image(self, object_key: str) -> ImagePayload: ...


class VisionTagger(Protocol):
    async def describe(
        self,
        image: ImagePayload,
        *,
        selection: FeedSelection | None = None,
    ) -> VisionAnalysis: ...


class ImageEmbedder(Protocol):
    async def embed(self, image: ImagePayload) -> EmbeddingResult: ...


class CaptureProcessor:
    def __init__(
        self,
        *,
        captures: CaptureWorkReader,
        jobs: WorkJobRepository,
        wardrobe: WardrobeWriter,
        objects: ImageReader,
        vision: VisionTagger,
        embedder: ImageEmbedder,
        segmenter: PromptableSegmentationPort | None = None,
        selection_images: SelectionImageRenderer | None = None,
    ) -> None:
        self._captures = captures
        self._jobs = jobs
        self._wardrobe = wardrobe
        self._objects = objects
        self._vision = vision
        self._embedder = embedder
        self._segmenter = segmenter
        self._selection_images = selection_images

    async def process(self, capture_id: UUID, job_id: UUID) -> ProcessingOutcome:
        capture = await self._captures.get_capture(capture_id)
        job = await self._jobs.get_job(job_id)
        if capture is None or job is None or job.capture_id != capture_id:
            raise LookupError("capture processing input does not exist")
        if job.state is JobState.READY:
            return ProcessingOutcome.ready()
        if job.state is JobState.PROCESSING:
            return ProcessingOutcome(state=JobState.PROCESSING, retryable=False)
        if job.state is JobState.ERROR:
            job = await self._jobs.update(job.transition(JobState.QUEUED))
        job = await self._jobs.update(job.transition(JobState.PROCESSING))

        if capture.source.kind is CaptureSourceKind.FEED:
            return await self._process_feed(capture, job)
        return await self._process_whole_capture(capture, job)

    async def _process_whole_capture(
        self,
        capture: Capture,
        job: ProcessingJob,
    ) -> ProcessingOutcome:
        item = await self._processing_item(capture, WHOLE_CAPTURE_SELECTION_KEY)
        try:
            image = self._objects.read_image(capture.source.object_key)
        except (FileNotFoundError, KeyError):
            error = ProviderError(
                "source_unavailable",
                "The original image is no longer available",
                retryable=False,
            )
            await self._wardrobe.save(item.with_status(ItemStatus.ERROR))
            await self._jobs.update(
                job.transition(
                    JobState.ERROR,
                    error_code=error.code,
                    error_message=error.message,
                )
            )
            return ProcessingOutcome.error(error)

        try:
            analysis = await self._vision.describe(image)
        except ProviderError as error:
            await self._wardrobe.save(item.with_status(ItemStatus.ERROR))
            await self._jobs.update(
                job.transition(
                    JobState.ERROR,
                    error_code=error.code,
                    error_message=error.message,
                )
            )
            return ProcessingOutcome.error(error)

        item = await self._wardrobe.save(
            item.apply_model(
                analysis.fields,
                analysis.metadata.as_dict(),
            )
        )
        try:
            embedding = await self._embedder.embed(image)
        except ProviderError as error:
            await self._wardrobe.save(item.with_status(ItemStatus.PARTIAL))
            await self._jobs.update(
                job.transition(
                    JobState.PARTIAL,
                    error_code=error.code,
                    error_message=error.message,
                )
            )
            return ProcessingOutcome.partial(error)

        await self._wardrobe.save(
            item.with_embedding(
                embedding.vector,
                model_version=embedding.model_version,
            ).with_status(ItemStatus.READY)
        )
        await self._jobs.update(job.transition(JobState.READY))
        return ProcessingOutcome.ready()

    async def _process_feed(
        self,
        capture: Capture,
        job: ProcessingJob,
    ) -> ProcessingOutcome:
        context = capture.feed_context
        if context is None:
            error = ProviderError(
                "feed_context_unavailable",
                "The Feed selection context is unavailable",
                retryable=False,
            )
            await self._jobs.update(
                job.transition(
                    JobState.ERROR,
                    error_code=error.code,
                    error_message=error.message,
                )
            )
            return ProcessingOutcome.error(error)

        items = {
            selection.selection_key: await self._processing_item(
                capture,
                selection.selection_key,
            )
            for selection in context.selections
        }
        try:
            frame = self._objects.read_image(capture.source.object_key)
        except (FileNotFoundError, KeyError):
            error = ProviderError(
                "source_unavailable",
                "The original image is no longer available",
                retryable=False,
            )
            for item in items.values():
                await self._wardrobe.save(item.with_status(ItemStatus.ERROR))
            await self._jobs.update(
                job.transition(
                    JobState.ERROR,
                    error_code=error.code,
                    error_message=error.message,
                )
            )
            return ProcessingOutcome.error(error)

        failures: list[ProviderError] = []
        for selection in context.selections:
            item = items[selection.selection_key]
            try:
                selected_image, segmentation = self._prepare_feed_selection(
                    frame,
                    selection,
                )
                item = await self._wardrobe.save(
                    item.with_model_metadata(
                        {
                            "segmentation": _segmentation_metadata(segmentation),
                        }
                    )
                )
                analysis = await self._vision.describe(
                    selected_image,
                    selection=selection,
                )
                item = await self._wardrobe.save(
                    item.apply_model(
                        analysis.fields,
                        analysis.metadata.as_dict(),
                    )
                )
                embedding = await self._embedder.embed(selected_image)
                await self._wardrobe.save(
                    item.with_embedding(
                        embedding.vector,
                        model_version=embedding.model_version,
                    ).with_status(ItemStatus.READY)
                )
            except ProviderError as error:
                failures.append(error)
                await self._wardrobe.save(
                    item.with_model_metadata(
                        {
                            "processing_error": {
                                "code": error.code,
                                "retryable": error.retryable,
                            }
                        }
                    ).with_status(ItemStatus.PARTIAL)
                )

        if failures:
            batch_error = next(
                (failure for failure in failures if failure.retryable),
                failures[0],
            )
            await self._jobs.update(
                job.transition(
                    JobState.PARTIAL,
                    error_code=batch_error.code,
                    error_message=batch_error.message,
                )
            )
            return ProcessingOutcome.partial(batch_error)

        await self._jobs.update(job.transition(JobState.READY))
        return ProcessingOutcome.ready()

    async def _processing_item(
        self,
        capture: Capture,
        selection_key: str,
    ) -> WardrobeItem:
        item = await self._wardrobe.get_by_capture(capture.id, selection_key)
        if item is None:
            return await self._wardrobe.save(
                WardrobeItem.processing(
                    capture,
                    selection_key=selection_key,
                )
            )
        return await self._wardrobe.save(
            item.with_model_metadata({"processing_error": None}).with_status(ItemStatus.PROCESSING)
        )

    def _prepare_feed_selection(
        self,
        frame: ImagePayload,
        selection: FeedSelection,
    ) -> tuple[ImagePayload, SegmentationResult]:
        if self._segmenter is None or self._selection_images is None:
            raise ProviderError(
                "feed_selection_processing_unavailable",
                "Feed selection processing is temporarily unavailable",
                retryable=True,
            )
        segmentation = self._segmenter.segment(
            SegmentationPrompt(
                frame=frame,
                selection=selection,
                fallback_reason="refinement_unavailable",
            )
        )
        if segmentation.selection_key != selection.selection_key:
            raise ProviderError(
                "segmentation_selection_mismatch",
                "Segmentation returned a different selection identity",
                retryable=False,
            )
        return self._selection_images.render(frame, segmentation), segmentation


def _segmentation_metadata(result: SegmentationResult) -> dict[str, object]:
    return {
        "selection_key": result.selection_key,
        "representation": result.metadata.representation.value,
        "refined": result.metadata.refined,
        "schema_version": result.metadata.schema_version,
        "latency_ms": result.metadata.latency_ms,
        "fallback_reason": result.metadata.fallback_reason,
        "provider": result.metadata.provider,
        "coarse_polygon": [{"x": point.x, "y": point.y} for point in result.coarse_polygon],
    }
