from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isclose, sqrt
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import Capture, JobState, ProcessingJob
from stylecapture_backend.features.wardrobe.domain import (
    ItemStatus,
    ModelField,
    WardrobeItem,
)


@dataclass(frozen=True, slots=True)
class ImagePayload:
    object_key: str
    content_type: str
    body: bytes
    sha256: str

    def __post_init__(self) -> None:
        if not self.body:
            raise ValueError("image body must not be empty")
        if not self.content_type.startswith("image/"):
            raise ValueError("content_type must describe an image")


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
        if len(self.vector) != 768:
            raise ValueError("fashion embedding must have 768 dimensions")
        norm = sqrt(sum(value * value for value in self.vector))
        if not isclose(norm, 1, rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError("fashion embedding must be L2-normalized")
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
    async def get_by_capture(self, capture_id: UUID) -> WardrobeItem | None: ...

    async def save(self, item: WardrobeItem) -> WardrobeItem: ...


class ImageReader(Protocol):
    def read_image(self, object_key: str) -> ImagePayload: ...


class VisionTagger(Protocol):
    async def describe(self, image: ImagePayload) -> VisionAnalysis: ...


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
    ) -> None:
        self._captures = captures
        self._jobs = jobs
        self._wardrobe = wardrobe
        self._objects = objects
        self._vision = vision
        self._embedder = embedder

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

        item = await self._wardrobe.get_by_capture(capture_id)
        if item is None:
            item = await self._wardrobe.save(WardrobeItem.processing(capture))
        else:
            item = await self._wardrobe.save(item.with_status(ItemStatus.PROCESSING))
        image = self._objects.read_image(capture.source.object_key)

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
