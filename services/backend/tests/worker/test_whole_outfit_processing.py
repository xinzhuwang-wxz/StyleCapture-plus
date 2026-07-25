from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    FeedCaptureIntent,
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
from stylecapture_backend.features.look.domain import (
    Look,
    LookAnalysis,
    LookAnalysisField,
    LookAnalysisMetadata,
    LookComponent,
    LookComponentStatus,
    LookDetail,
    LookStatus,
    PreferenceSignal,
)
from stylecapture_backend.features.wardrobe.domain import ItemStatus, ModelField, WardrobeItem
from stylecapture_backend.features.wardrobe.taxonomy import GarmentCategory

OUTFIT_SELECTION_KEY = "whole-outfit"


def assert_no_provider_identity(payload: object) -> None:
    serialized = json.dumps(_jsonable(payload), sort_keys=True)
    assert "provider_model" not in serialized
    assert "internal-provider-id" not in serialized
    assert "provider-model-v1" not in serialized
    assert "provider-outfit-v1" not in serialized


def _jsonable(payload: object) -> object:
    if isinstance(payload, Mapping):
        return {str(key): _jsonable(value) for key, value in payload.items()}
    if isinstance(payload, tuple | list):
        return [_jsonable(value) for value in payload]
    return payload


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
            raise AssertionError("processor attempted to replace a stable Item")
        self.items[identity] = item
        return item


class MemoryLookRepository:
    def __init__(self, look: Look) -> None:
        self.look = look
        self.components: dict[str, LookComponent] = {}

    async def ensure_placeholder(self, look: Look, signal: PreferenceSignal) -> Look:
        del look, signal
        return self.look

    async def list_for_user(self, user_id: UUID) -> list[Look]:
        return [self.look] if user_id == self.look.user_id else []

    async def get_detail_for_user(
        self,
        look_id: UUID,
        user_id: UUID,
    ) -> LookDetail | None:
        if look_id != self.look.id or user_id != self.look.user_id:
            return None
        return LookDetail(
            look=self.look,
            components=tuple(
                sorted(
                    self.components.values(),
                    key=lambda component: component.display_order,
                )
            ),
            preference_signals=(),
        )

    async def get_by_capture(
        self,
        capture_id: UUID,
        source_selection_key: str,
    ) -> Look | None:
        if (
            capture_id == self.look.capture_id
            and source_selection_key == self.look.source_selection_key
        ):
            return self.look
        return None

    async def save(self, look: Look) -> Look:
        if look.id != self.look.id:
            raise AssertionError("processor attempted to replace the stable Look")
        self.look = look
        return look

    async def save_component(self, component: LookComponent) -> LookComponent:
        current = self.components.get(component.component_key)
        if current is not None and current.id != component.id:
            raise AssertionError("processor attempted to replace a stable component")
        self.components[component.component_key] = component
        return component

    async def append_preference(self, signal: PreferenceSignal) -> PreferenceSignal:
        return signal


@dataclass(frozen=True)
class MemoryObjects:
    payload: ImagePayload
    derived: dict[str, ImagePayload] | None = None

    def read_image(self, object_key: str) -> ImagePayload:
        if object_key != self.payload.object_key:
            raise KeyError(object_key)
        return self.payload

    def write_derived_image(
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
        stored = ImagePayload(
            object_key=f"{prefix.rstrip('/')}/{image.sha256}.png",
            content_type="image/png",
            body=image.body,
            sha256=image.sha256,
        )
        derived.setdefault(stored.object_key, stored)
        return stored


class RecordingGrounder:
    def __init__(
        self,
        candidates: tuple[GroundingCandidate, ...] = (),
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
                latency_ms=5,
            ),
        )


class RecordingSegmenter:
    def __init__(self, failing_keys: set[str] | None = None) -> None:
        self.failing_keys = failing_keys or set()
        self.prompts: list[SegmentationPrompt] = []

    def segment(self, prompt: SegmentationPrompt) -> SegmentationResult:
        self.prompts.append(prompt)
        if prompt.selection.selection_key in self.failing_keys:
            raise ProviderError(
                "segmentation_unavailable",
                "Segmentation is temporarily unavailable",
                retryable=True,
            )
        return SegmentationResult(
            selection_key=prompt.selection.selection_key,
            coarse_polygon=prompt.selection.polygon,
            mask=None,
            metadata=SegmentationMetadata(
                provider="deterministic_lasso_fallback",
                representation=SegmentationRepresentation.COARSE_POLYGON,
                refined=False,
                schema_version="feed-segmentation-v1",
                latency_ms=0,
                fallback_reason=prompt.fallback_reason,
            ),
        )


class SelectionImages:
    def render(self, frame: ImagePayload, segmentation: SegmentationResult) -> ImagePayload:
        digest = {
            "linen_shirt": "1" * 64,
            "wide_trousers": "2" * 64,
            "whole-outfit": "3" * 64,
        }.get(segmentation.selection_key, "4" * 64)
        return ImagePayload(
            object_key=f"{frame.object_key}#selection={segmentation.selection_key}",
            content_type="image/png",
            body=f"pixels:{segmentation.selection_key}".encode(),
            sha256=digest,
        )


class RecordingVision:
    def __init__(self, failing_keys: set[str] | None = None) -> None:
        self.failing_keys = failing_keys or set()
        self.calls: list[FeedSelection | None] = []

    async def describe(
        self,
        image: ImagePayload,
        *,
        selection: FeedSelection | None = None,
    ) -> VisionAnalysis:
        del image
        self.calls.append(selection)
        assert selection is not None
        if selection.selection_key in self.failing_keys:
            raise ProviderError(
                "vision_unavailable",
                "Vision is temporarily unavailable",
                retryable=True,
            )
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
    def __init__(self, failing_sha256: set[str] | None = None) -> None:
        self.failing_sha256 = failing_sha256 or set()

    async def embed(self, image: ImagePayload) -> EmbeddingResult:
        if image.sha256 in self.failing_sha256:
            raise ProviderError(
                "embedding_unavailable",
                "Embedding is temporarily unavailable",
                retryable=True,
            )
        return EmbeddingResult(
            vector=(1.0,) + (0.0,) * 2047,
            model_version="doubao-embedding-vision-250615",
        )


class FixedOutfitAnalyzer:
    def __init__(self, error: ProviderError | None = None) -> None:
        self.error = error
        self.calls: list[tuple[ImagePayload, tuple[LookComponent, ...]]] = []

    async def analyze(
        self,
        image: ImagePayload,
        *,
        components: tuple[LookComponent, ...],
    ) -> LookAnalysis:
        self.calls.append((image, components))
        if self.error is not None:
            raise self.error
        return LookAnalysis(
            color=LookAnalysisField("cream and navy", 0.9),
            silhouette=LookAnalysisField("relaxed", 0.87),
            material=LookAnalysisField("linen and cotton", 0.8),
            layering=LookAnalysisField("shirt over trousers", 0.84),
            focal_point=LookAnalysisField("open collar", 0.79),
            scene=LookAnalysisField("street style", 0.76),
            style=LookAnalysisField("minimal casual", 0.92),
            metadata=LookAnalysisMetadata(
                capability_alias="outfit_analysis",
                provider_model="server_private",
                prompt_version="outfit-analysis-v1",
                schema_version="look-analysis-v1",
                taxonomy_version="stylecapture-v1",
                latency_ms=8,
            ),
        )


def box_candidate(
    label: str,
    box: NormalizedBox,
    *,
    confidence: float = 0.91,
    visible_fraction: float = 0.9,
    category: GarmentCategory = GarmentCategory.TOPS,
) -> GroundingCandidate:
    return GroundingCandidate(
        label=label,
        category=category,
        box=box,
        confidence=confidence,
        visible_fraction=visible_fraction,
    )


def whole_outfit_capture_job() -> tuple[Capture, ProcessingJob]:
    selection = FeedSelection(
        selection_key=OUTFIT_SELECTION_KEY,
        polygon=(
            NormalizedPoint(0.1, 0.1),
            NormalizedPoint(0.9, 0.1),
            NormalizedPoint(0.9, 0.9),
            NormalizedPoint(0.1, 0.9),
        ),
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
            selections=(selection,),
            intent=FeedCaptureIntent.WHOLE_OUTFIT,
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
    grounder: RecordingGrounder,
    segmenter: RecordingSegmenter | None = None,
    vision: RecordingVision | None = None,
    embedder: FixedEmbedder | None = None,
    outfit_analyzer: FixedOutfitAnalyzer | None = None,
) -> tuple[
    CaptureProcessor,
    MemoryWorkRepository,
    MemoryWardrobeRepository,
    MemoryLookRepository,
    MemoryObjects,
]:
    work = MemoryWorkRepository(capture, job)
    wardrobe = MemoryWardrobeRepository()
    look = Look.feed_saved(
        user_id=capture.user_id,
        capture_id=capture.id,
        source_selection_key=OUTFIT_SELECTION_KEY,
    )
    looks = MemoryLookRepository(look)
    objects = MemoryObjects(image_for(capture))
    processor = CaptureProcessor(
        captures=work,
        jobs=work,
        wardrobe=wardrobe,
        objects=objects,
        vision=vision or RecordingVision(),
        embedder=embedder or FixedEmbedder(),
        segmenter=segmenter or RecordingSegmenter(),
        selection_images=SelectionImages(),
        display_assets=objects,
        looks=looks,
        grounder=grounder,
        outfit_analyzer=outfit_analyzer or FixedOutfitAnalyzer(),
    )
    return processor, work, wardrobe, looks, objects


@pytest.mark.asyncio
async def test_whole_outfit_creates_components_items_display_assets_and_analysis() -> None:
    capture, job = whole_outfit_capture_job()
    grounder = RecordingGrounder(
        (
            box_candidate("linen_shirt", NormalizedBox(150, 160, 620, 520)),
            box_candidate(
                "wide_trousers",
                NormalizedBox(220, 520, 700, 870),
                category=GarmentCategory.BOTTOMS,
            ),
        )
    )
    processor, work, wardrobe, looks, objects = build_processor(
        capture,
        job,
        grounder=grounder,
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome == ProcessingOutcome.ready()
    assert work.job.state is JobState.READY
    assert looks.look.status is LookStatus.READY
    assert looks.look.display_object_key == "derived/looks/" + "3" * 64 + ".png"
    assert objects.derived is not None
    assert set(objects.derived) == {
        "derived/items/" + "1" * 64 + ".png",
        "derived/items/" + "2" * 64 + ".png",
        "derived/looks/" + "3" * 64 + ".png",
    }
    assert set(wardrobe.items) == {
        (capture.id, "linen_shirt"),
        (capture.id, "wide_trousers"),
    }
    assert [component.component_key for component in looks.components.values()] == [
        "linen_shirt",
        "wide_trousers",
    ]
    assert all(component.status is LookComponentStatus.READY for component in looks.components.values())
    assert {
        component.item_id for component in looks.components.values()
    } == {item.id for item in wardrobe.items.values()}
    assert all(item.status is ItemStatus.READY for item in wardrobe.items.values())
    assert looks.look.analysis is not None
    assert looks.look.analysis.metadata.capability_alias == "outfit_analysis"
    assert looks.look.analysis.metadata.provider_model == "server_private"
    assert looks.look.analysis.style.value == "minimal casual"
    assert_no_provider_identity(looks.look.analysis.metadata.provider_model)
    for item in wardrobe.items.values():
        assert_no_provider_identity(item.model_metadata)
    for component in looks.components.values():
        assert_no_provider_identity(component.grounding_metadata)


@pytest.mark.asyncio
async def test_whole_outfit_filters_outside_lasso_and_low_confidence_candidates() -> None:
    capture, job = whole_outfit_capture_job()
    grounder = RecordingGrounder(
        (
            box_candidate("inside_shirt", NormalizedBox(150, 150, 500, 450)),
            box_candidate("outside_hat", NormalizedBox(0, 0, 80, 80)),
            box_candidate("weak_bag", NormalizedBox(300, 300, 400, 400), confidence=0.49),
        )
    )
    processor, work, wardrobe, looks, _ = build_processor(capture, job, grounder=grounder)

    outcome = await processor.process(capture.id, job.id)

    assert outcome == ProcessingOutcome.ready()
    assert work.job.state is JobState.READY
    assert set(wardrobe.items) == {(capture.id, "inside_shirt")}
    assert set(looks.components) == {"inside_shirt"}
    assert looks.look.status is LookStatus.READY


@pytest.mark.asyncio
async def test_component_failure_preserves_successful_components_and_marks_look_partial() -> None:
    capture, job = whole_outfit_capture_job()
    grounder = RecordingGrounder(
        (
            box_candidate("linen_shirt", NormalizedBox(150, 160, 620, 520)),
            box_candidate("wide_trousers", NormalizedBox(220, 520, 700, 870)),
        )
    )
    processor, work, wardrobe, looks, _ = build_processor(
        capture,
        job,
        grounder=grounder,
        segmenter=RecordingSegmenter(failing_keys={"wide_trousers"}),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.PARTIAL
    assert outcome.retryable is True
    assert outcome.error_code == "segmentation_unavailable"
    assert work.job.state is JobState.PARTIAL
    assert looks.look.status is LookStatus.PARTIAL
    assert set(wardrobe.items) == {(capture.id, "linen_shirt")}
    assert looks.components["linen_shirt"].status is LookComponentStatus.READY
    assert looks.components["wide_trousers"].status is LookComponentStatus.ERROR
    assert looks.components["wide_trousers"].item_id is None


@pytest.mark.asyncio
async def test_vision_failure_creates_no_item_for_component() -> None:
    capture, job = whole_outfit_capture_job()
    grounder = RecordingGrounder(
        (box_candidate("linen_shirt", NormalizedBox(150, 160, 620, 520)),)
    )
    processor, work, wardrobe, looks, _ = build_processor(
        capture,
        job,
        grounder=grounder,
        vision=RecordingVision(failing_keys={"linen_shirt"}),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.PARTIAL
    assert outcome.error_code == "vision_unavailable"
    assert work.job.state is JobState.PARTIAL
    assert not wardrobe.items
    assert looks.components["linen_shirt"].status is LookComponentStatus.ERROR
    assert looks.components["linen_shirt"].item_id is None


@pytest.mark.asyncio
async def test_embedding_failure_creates_no_item_for_component() -> None:
    capture, job = whole_outfit_capture_job()
    grounder = RecordingGrounder(
        (box_candidate("linen_shirt", NormalizedBox(150, 160, 620, 520)),)
    )
    processor, work, wardrobe, looks, _ = build_processor(
        capture,
        job,
        grounder=grounder,
        embedder=FixedEmbedder(failing_sha256={"1" * 64}),
    )

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.PARTIAL
    assert outcome.error_code == "embedding_unavailable"
    assert work.job.state is JobState.PARTIAL
    assert not wardrobe.items
    assert looks.components["linen_shirt"].status is LookComponentStatus.ERROR
    assert looks.components["linen_shirt"].item_id is None


@pytest.mark.asyncio
async def test_invalid_long_grounding_label_is_retryable_without_stranding_processing() -> None:
    capture, job = whole_outfit_capture_job()
    long_label = "a" * 65
    grounder = RecordingGrounder(
        (box_candidate(long_label, NormalizedBox(150, 160, 620, 520)),)
    )
    processor, work, wardrobe, looks, _ = build_processor(capture, job, grounder=grounder)

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.PARTIAL
    assert outcome.retryable is True
    assert outcome.error_code == "grounding_schema_invalid"
    assert work.job.state is JobState.PARTIAL
    assert not wardrobe.items
    assert not looks.components
    assert looks.look.status is LookStatus.PROCESSING


@pytest.mark.asyncio
async def test_whole_outfit_retry_reuses_look_component_item_and_asset_identities() -> None:
    capture, job = whole_outfit_capture_job()
    grounder = RecordingGrounder(
        (
            box_candidate("linen_shirt", NormalizedBox(150, 160, 620, 520)),
            box_candidate("wide_trousers", NormalizedBox(220, 520, 700, 870)),
        )
    )
    segmenter = RecordingSegmenter(failing_keys={"wide_trousers"})
    processor, _work, wardrobe, looks, objects = build_processor(
        capture,
        job,
        grounder=grounder,
        segmenter=segmenter,
    )

    first_outcome = await processor.process(capture.id, job.id)
    first_component_ids = {
        key: component.id for key, component in looks.components.items()
    }
    first_item_ids = {key: item.id for (_, key), item in wardrobe.items.items()}
    first_asset_keys = set(objects.derived or {})

    segmenter.failing_keys.clear()
    second_outcome = await processor.process(capture.id, job.id)

    assert first_outcome.state is JobState.PARTIAL
    assert second_outcome == ProcessingOutcome.ready()
    assert {key: component.id for key, component in looks.components.items()} == first_component_ids
    assert {key: item.id for (_, key), item in wardrobe.items.items()} == {
        **first_item_ids,
        "wide_trousers": wardrobe.items[(capture.id, "wide_trousers")].id,
    }
    assert len(wardrobe.items) == 2
    assert len(objects.derived or {}) == 3
    assert first_asset_keys <= set(objects.derived or {})
    assert looks.look.status is LookStatus.READY


@pytest.mark.asyncio
async def test_retry_keeps_look_partial_when_existing_error_component_disappears_from_grounding() -> None:
    capture, job = whole_outfit_capture_job()
    grounder = RecordingGrounder(
        (
            box_candidate("linen_shirt", NormalizedBox(150, 160, 620, 520)),
            box_candidate("wide_trousers", NormalizedBox(220, 520, 700, 870)),
        )
    )
    segmenter = RecordingSegmenter(failing_keys={"wide_trousers"})
    processor, work, wardrobe, looks, _ = build_processor(
        capture,
        job,
        grounder=grounder,
        segmenter=segmenter,
    )

    first_outcome = await processor.process(capture.id, job.id)
    segmenter.failing_keys.clear()
    grounder.candidates = (
        box_candidate("linen_shirt", NormalizedBox(150, 160, 620, 520)),
    )
    second_outcome = await processor.process(capture.id, job.id)

    assert first_outcome.state is JobState.PARTIAL
    assert second_outcome.state is JobState.PARTIAL
    assert second_outcome.retryable is True
    assert second_outcome.error_code == "component_unresolved"
    assert work.job.state is JobState.PARTIAL
    assert set(wardrobe.items) == {(capture.id, "linen_shirt")}
    assert looks.components["wide_trousers"].status is LookComponentStatus.ERROR
    assert looks.look.status is LookStatus.PARTIAL


@pytest.mark.asyncio
async def test_grounding_failure_is_sanitized_and_keeps_placeholder_retryable() -> None:
    capture, job = whole_outfit_capture_job()
    grounder = RecordingGrounder(
        error=ProviderError(
            "grounding_unavailable",
            "Visual grounding is temporarily unavailable",
            retryable=True,
        )
    )
    processor, work, wardrobe, looks, _ = build_processor(capture, job, grounder=grounder)

    outcome = await processor.process(capture.id, job.id)

    assert outcome.state is JobState.PARTIAL
    assert outcome.retryable is True
    assert outcome.error_code == "grounding_unavailable"
    assert work.job.state is JobState.PARTIAL
    assert work.job.error_message == "Visual grounding is temporarily unavailable"
    assert not wardrobe.items
    assert not looks.components
    assert looks.look.status is LookStatus.PROCESSING
    assert looks.look.display_object_key == "derived/looks/" + "3" * 64 + ".png"
