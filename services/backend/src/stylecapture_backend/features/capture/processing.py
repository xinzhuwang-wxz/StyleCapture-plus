from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isclose, sqrt
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSourceKind,
    FeedCaptureIntent,
    FeedSelection,
    ImagePayload,
    JobState,
    NormalizedPoint,
    ProcessingJob,
    is_valid_selection_key,
)
from stylecapture_backend.features.capture.feed_media import (
    PromptableSegmentationPort,
    SegmentationPrompt,
    SegmentationResult,
    SelectionImageRenderer,
)
from stylecapture_backend.features.look.domain import (
    Look,
    LookAnalysis,
    LookComponent,
    LookComponentStatus,
    LookDetail,
    LookStatus,
)
from stylecapture_backend.features.wardrobe.domain import (
    WHOLE_CAPTURE_SELECTION_KEY,
    ItemStatus,
    ModelField,
    WardrobeItem,
)

if TYPE_CHECKING:
    from stylecapture_backend.features.capture.grounding import (
        GroundingAnalysis,
        GroundingCandidate,
        NormalizedBox,
        VisualGroundingPort,
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


class DerivedImageWriter(Protocol):
    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload: ...


class VisionTagger(Protocol):
    async def describe(
        self,
        image: ImagePayload,
        *,
        selection: FeedSelection | None = None,
    ) -> VisionAnalysis: ...


class ImageEmbedder(Protocol):
    async def embed(self, image: ImagePayload) -> EmbeddingResult: ...


class LookProcessingRepository(Protocol):
    async def get_by_capture(
        self,
        capture_id: UUID,
        source_selection_key: str,
    ) -> Look | None: ...

    async def get_detail_for_user(
        self,
        look_id: UUID,
        user_id: UUID,
    ) -> LookDetail | None: ...

    async def save(self, look: Look) -> Look: ...

    async def save_component(self, component: LookComponent) -> LookComponent: ...


class OutfitAnalyzer(Protocol):
    async def analyze(
        self,
        image: ImagePayload,
        *,
        components: tuple[LookComponent, ...],
    ) -> LookAnalysis: ...


class CaptureProcessor:
    _MIN_COMPONENT_CONFIDENCE = 0.5
    _MIN_VISIBLE_FRACTION = 0.5

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
        display_assets: DerivedImageWriter | None = None,
        looks: LookProcessingRepository | None = None,
        grounder: VisualGroundingPort | None = None,
        outfit_analyzer: OutfitAnalyzer | None = None,
    ) -> None:
        self._captures = captures
        self._jobs = jobs
        self._wardrobe = wardrobe
        self._objects = objects
        self._vision = vision
        self._embedder = embedder
        self._segmenter = segmenter
        self._selection_images = selection_images
        self._display_assets = display_assets
        self._looks = looks
        self._grounder = grounder
        self._outfit_analyzer = outfit_analyzer

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

        if context.intent is FeedCaptureIntent.WHOLE_OUTFIT:
            return await self._process_whole_outfit_feed(capture, job)

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
                if self._display_assets is None:
                    raise ProviderError(
                        "display_asset_storage_unavailable",
                        "Wardrobe display asset storage is temporarily unavailable",
                        retryable=True,
                    )
                display_image = self._display_assets.write_derived_image(
                    selected_image,
                    owner_id=capture.user_id,
                    prefix="derived/items",
                )
                item = await self._wardrobe.save(
                    item.with_display_object(display_image.object_key).with_model_metadata(
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

    async def _process_whole_outfit_feed(
        self,
        capture: Capture,
        job: ProcessingJob,
    ) -> ProcessingOutcome:
        context = capture.feed_context
        if context is None or len(context.selections) != 1:
            error = ProviderError(
                "whole_outfit_context_invalid",
                "Whole-outfit processing requires exactly one Feed selection",
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

        if (
            self._looks is None
            or self._grounder is None
            or self._outfit_analyzer is None
            or self._segmenter is None
            or self._selection_images is None
            or self._display_assets is None
        ):
            error = ProviderError(
                "whole_outfit_processing_unavailable",
                "Whole-outfit processing is temporarily unavailable",
                retryable=True,
            )
            await self._jobs.update(
                job.transition(
                    JobState.PARTIAL,
                    error_code=error.code,
                    error_message=error.message,
                )
            )
            return ProcessingOutcome.partial(error)

        outfit_selection = context.selections[0]
        look = await self._looks.get_by_capture(capture.id, outfit_selection.selection_key)
        if look is None:
            error = ProviderError(
                "look_placeholder_unavailable",
                "The saved Look placeholder is unavailable",
                retryable=True,
            )
            await self._jobs.update(
                job.transition(
                    JobState.PARTIAL,
                    error_code=error.code,
                    error_message=error.message,
                )
            )
            return ProcessingOutcome.partial(error)

        try:
            frame = self._objects.read_image(capture.source.object_key)
        except (FileNotFoundError, KeyError):
            error = ProviderError(
                "source_unavailable",
                "The original image is no longer available",
                retryable=False,
            )
            await self._looks.save(look.with_status(LookStatus.ERROR))
            await self._jobs.update(
                job.transition(
                    JobState.ERROR,
                    error_code=error.code,
                    error_message=error.message,
                )
            )
            return ProcessingOutcome.error(error)

        try:
            look = await self._save_look_display_asset(
                look,
                frame,
                outfit_selection,
                capture.user_id,
            )
            grounding = await self._grounder.ground(frame, scope=outfit_selection)
        except ProviderError as error:
            await self._jobs.update(
                job.transition(
                    JobState.PARTIAL,
                    error_code=error.code,
                    error_message=error.message,
                )
            )
            return ProcessingOutcome.partial(error)

        failures: list[ProviderError] = []
        ready_components: list[LookComponent] = []
        existing_components = await self._component_index(look)
        invalid_candidate = self._invalid_processable_candidate(grounding, outfit_selection)
        if invalid_candidate is not None:
            invalid_grounding_error = ProviderError(
                "grounding_schema_invalid",
                "Visual grounding returned an invalid component identity",
                retryable=True,
            )
            await self._jobs.update(
                job.transition(
                    JobState.PARTIAL,
                    error_code=invalid_grounding_error.code,
                    error_message=invalid_grounding_error.message,
                )
            )
            return ProcessingOutcome.partial(invalid_grounding_error)

        accepted = self._reliable_candidates(grounding, outfit_selection)
        accepted_keys = {candidate.label for candidate in accepted}
        for display_order, candidate in enumerate(accepted):
            component = existing_components.get(candidate.label) or LookComponent.pending(
                look_id=look.id,
                component_key=candidate.label,
                evidence_region=_box_polygon(candidate.box),
                confidence=candidate.confidence,
                grounding_metadata=_grounding_metadata(grounding.metadata, candidate),
                role=candidate.category.value,
                display_order=display_order,
            )
            if component.status is LookComponentStatus.READY and component.item_id is not None:
                ready_components.append(component)
                continue

            component = await self._looks.save_component(
                component.with_status(LookComponentStatus.PROCESSING)
            )
            component_selection = FeedSelection(
                selection_key=component.component_key,
                polygon=component.evidence_region,
            )
            try:
                selected_image, segmentation = self._prepare_feed_selection(
                    frame,
                    component_selection,
                )
                display_image = self._display_assets.write_derived_image(
                    selected_image,
                    owner_id=capture.user_id,
                    prefix="derived/items",
                )
                item = await self._item_candidate(capture, component.component_key)
                item = item.with_display_object(display_image.object_key).with_model_metadata(
                    {
                        "segmentation": _segmentation_metadata(segmentation),
                        "grounding": _grounding_metadata(grounding.metadata, candidate),
                        "processing_error": None,
                    }
                )
                analysis = await self._vision.describe(
                    selected_image,
                    selection=component_selection,
                )
                item = item.apply_model(
                    analysis.fields,
                    analysis.metadata.as_dict(),
                )
                embedding = await self._embedder.embed(selected_image)
                item = await self._wardrobe.save(
                    item.with_embedding(
                        embedding.vector,
                        model_version=embedding.model_version,
                    ).with_status(ItemStatus.READY)
                )
                component = await self._looks.save_component(component.with_item(item.id))
                ready_components.append(component)
            except ProviderError as error:
                failures.append(error)
                await self._looks.save_component(component.with_status(LookComponentStatus.ERROR))

        unresolved = tuple(
            component
            for key, component in existing_components.items()
            if key not in accepted_keys and component.status is not LookComponentStatus.READY
        )
        if unresolved:
            failures.append(
                ProviderError(
                    "component_unresolved",
                    "A previously detected outfit component is still unresolved",
                    retryable=True,
                )
            )

        if not ready_components and not accepted and not unresolved:
            no_components_error = ProviderError(
                "no_reliable_components",
                "No reliable outfit components were found",
                retryable=False,
            )
            await self._looks.save(look.with_status(LookStatus.ERROR))
            await self._jobs.update(
                job.transition(
                    JobState.ERROR,
                    error_code=no_components_error.code,
                    error_message=no_components_error.message,
                )
            )
            return ProcessingOutcome.error(no_components_error)

        try:
            if ready_components:
                look = await self._looks.save(
                    look.with_analysis(
                        await self._outfit_analyzer.analyze(
                            frame,
                            components=tuple(ready_components),
                        )
                    )
                )
        except ProviderError as error:
            failures.append(error)

        if failures:
            batch_error = next(
                (failure for failure in failures if failure.retryable),
                failures[0],
            )
            await self._looks.save(look.with_status(LookStatus.PARTIAL))
            await self._jobs.update(
                job.transition(
                    JobState.PARTIAL,
                    error_code=batch_error.code,
                    error_message=batch_error.message,
                )
            )
            return ProcessingOutcome.partial(batch_error)

        await self._looks.save(look.with_status(LookStatus.READY))
        await self._jobs.update(job.transition(JobState.READY))
        return ProcessingOutcome.ready()

    async def _save_look_display_asset(
        self,
        look: Look,
        frame: ImagePayload,
        selection: FeedSelection,
        user_id: UUID,
    ) -> Look:
        if look.display_object_key is not None:
            return look
        assert self._display_assets is not None
        assert self._looks is not None
        selected_image, _ = self._prepare_feed_selection(frame, selection)
        display_image = self._display_assets.write_derived_image(
            selected_image,
            owner_id=user_id,
            prefix="derived/looks",
        )
        return await self._looks.save(look.with_display_object(display_image.object_key))

    async def _component_index(self, look: Look) -> dict[str, LookComponent]:
        assert self._looks is not None
        detail = await self._looks.get_detail_for_user(look.id, look.user_id)
        if detail is None:
            return {}
        return {component.component_key: component for component in detail.components}

    def _invalid_processable_candidate(
        self,
        grounding: GroundingAnalysis,
        selection: FeedSelection,
    ) -> GroundingCandidate | None:
        return next(
            (
                candidate
                for candidate in grounding.candidates
                if self._candidate_in_processing_scope(candidate, selection)
                and not is_valid_selection_key(candidate.label)
            ),
            None,
        )

    def _reliable_candidates(
        self,
        grounding: GroundingAnalysis,
        selection: FeedSelection,
    ) -> tuple[GroundingCandidate, ...]:
        return tuple(
            candidate
            for candidate in grounding.candidates
            if self._candidate_in_processing_scope(candidate, selection)
            and is_valid_selection_key(candidate.label)
        )

    def _candidate_in_processing_scope(
        self,
        candidate: GroundingCandidate,
        selection: FeedSelection,
    ) -> bool:
        return (
            candidate.confidence >= self._MIN_COMPONENT_CONFIDENCE
            and candidate.visible_fraction >= self._MIN_VISIBLE_FRACTION
            and _box_inside_polygon(candidate.box, selection.polygon)
        )

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

    async def _item_candidate(
        self,
        capture: Capture,
        selection_key: str,
    ) -> WardrobeItem:
        item = await self._wardrobe.get_by_capture(capture.id, selection_key)
        if item is None:
            return WardrobeItem.processing(capture, selection_key=selection_key)
        return item.with_model_metadata({"processing_error": None}).with_status(ItemStatus.PROCESSING)

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


def _grounding_metadata(
    metadata: ModelMetadata,
    candidate: GroundingCandidate,
) -> dict[str, object]:
    return {
        **metadata.as_dict(),
        "label": candidate.label,
        "category": candidate.category.value,
        "confidence": candidate.confidence,
        "visible_fraction": candidate.visible_fraction,
        "box": {
            "x_min": candidate.box.x_min,
            "y_min": candidate.box.y_min,
            "x_max": candidate.box.x_max,
            "y_max": candidate.box.y_max,
        },
    }


def _box_polygon(box: NormalizedBox) -> tuple[NormalizedPoint, ...]:
    return (
        _box_point(box.x_min, box.y_min),
        _box_point(box.x_max, box.y_min),
        _box_point(box.x_max, box.y_max),
        _box_point(box.x_min, box.y_max),
    )


def _box_point(x: int, y: int) -> NormalizedPoint:
    return NormalizedPoint(x / 999, y / 999)


def _box_inside_polygon(box: NormalizedBox, polygon: tuple[NormalizedPoint, ...]) -> bool:
    return all(_point_in_polygon(point, polygon) for point in _box_polygon(box))


def _point_in_polygon(point: NormalizedPoint, polygon: tuple[NormalizedPoint, ...]) -> bool:
    inside = False
    previous = polygon[-1]
    for current in polygon:
        intersects = (current.y > point.y) != (previous.y > point.y)
        if intersects:
            slope_x = (previous.x - current.x) * (point.y - current.y) / (
                previous.y - current.y
            ) + current.x
            if point.x <= slope_x:
                inside = not inside
        previous = current
    return inside or any(_point_on_segment(point, start, end) for start, end in _segments(polygon))


def _segments(
    polygon: tuple[NormalizedPoint, ...],
) -> tuple[tuple[NormalizedPoint, NormalizedPoint], ...]:
    return tuple(zip(polygon, polygon[1:] + polygon[:1], strict=True))


def _point_on_segment(
    point: NormalizedPoint,
    start: NormalizedPoint,
    end: NormalizedPoint,
) -> bool:
    cross = (point.y - start.y) * (end.x - start.x) - (point.x - start.x) * (
        end.y - start.y
    )
    if abs(cross) > 1e-9:
        return False
    return (
        min(start.x, end.x) - 1e-9 <= point.x <= max(start.x, end.x) + 1e-9
        and min(start.y, end.y) - 1e-9 <= point.y <= max(start.y, end.y) + 1e-9
    )
