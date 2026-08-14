from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from stylecapture_backend.features.capture.domain import NormalizedPoint
from stylecapture_backend.features.look.domain import (
    COMPOSITION_ITEM_EVIDENCE,
    Look,
    LookAnalysis,
    LookAnalysisField,
    LookAnalysisMetadata,
    LookComponent,
    LookComponentStatus,
    LookSource,
    LookStatus,
    PreferenceSignal,
    PreferenceSignalKind,
)


def analysis() -> LookAnalysis:
    field = LookAnalysisField(value="简洁通勤", confidence=0.88)
    return LookAnalysis(
        color=field,
        silhouette=field,
        material=field,
        layering=field,
        focal_point=field,
        scene=field,
        style=field,
        metadata=LookAnalysisMetadata(
            capability_alias="reasoning",
            model_version="test-model",
            prompt_version="outfit-v1",
            schema_version="look-analysis-v1",
            taxonomy_version="stylecapture-v1",
            latency_ms=12,
        ),
    )


def test_look_analysis_prefers_a_generated_title_and_keeps_style_as_legacy_fallback() -> None:
    legacy = analysis()
    titled = LookAnalysis(
        color=legacy.color,
        silhouette=legacy.silhouette,
        material=legacy.material,
        layering=legacy.layering,
        focal_point=legacy.focal_point,
        scene=legacy.scene,
        style=legacy.style,
        metadata=legacy.metadata,
        title=LookAnalysisField(value="米白松弛感", confidence=0.93),
    )

    assert legacy.display_name == "简洁通勤"
    assert titled.display_name == "米白松弛感"


def test_feed_saved_look_starts_as_a_processing_relationship_placeholder() -> None:
    user_id = uuid4()
    capture_id = uuid4()

    look = Look.feed_saved(
        user_id=user_id,
        capture_id=capture_id,
        source_selection_key="whole-look",
    )

    assert look.user_id == user_id
    assert look.capture_id == capture_id
    assert look.source_selection_key == "whole-look"
    assert look.source is LookSource.FEED_SAVED
    assert look.status is LookStatus.PROCESSING
    assert look.analysis is None
    assert look.display_object_key is None


def test_look_display_image_is_a_derived_asset_not_source_truth() -> None:
    look = Look.feed_saved(
        user_id=uuid4(),
        capture_id=uuid4(),
        source_selection_key="whole-look",
    )

    displayed = look.with_display_object("derived/looks/transparent-look.webp")

    assert displayed.display_object_key == "derived/looks/transparent-look.webp"
    assert displayed.capture_id == look.capture_id
    with pytest.raises(ValueError, match="display object key must not be empty"):
        look.with_display_object(" ")


def test_ai_composition_has_no_single_capture_or_frame_region_claim() -> None:
    look = Look.ai_generated(
        user_id=uuid4(),
        source_selection_key="ai123",
        analysis=analysis(),
    )
    component = LookComponent.pending(
        look_id=look.id,
        component_key="slot1",
        evidence_region=(),
        confidence=0,
        grounding_metadata={
            "evidence_type": COMPOSITION_ITEM_EVIDENCE,
            "item_id": str(uuid4()),
            "item_version": datetime.now(UTC).isoformat(),
        },
    ).with_item(uuid4())

    assert look.capture_id is None
    assert look.source is LookSource.AI_GENERATED
    assert component.evidence_region == ()
    assert component.confidence == 0

    with pytest.raises(
        ValueError,
        match="must not claim frame-region confidence",
    ):
        LookComponent.pending(
            look_id=look.id,
            component_key="slot2",
            evidence_region=(
                NormalizedPoint(0, 0),
                NormalizedPoint(1, 0),
                NormalizedPoint(1, 1),
            ),
            confidence=1,
            grounding_metadata={"evidence_type": COMPOSITION_ITEM_EVIDENCE},
        )


def test_only_a_ready_component_may_reference_a_real_item() -> None:
    component = LookComponent.pending(
        look_id=uuid4(),
        component_key="outerwear-1",
        evidence_region=(
            NormalizedPoint(0.1, 0.1),
            NormalizedPoint(0.8, 0.1),
            NormalizedPoint(0.8, 0.9),
        ),
        confidence=0.72,
        grounding_metadata={"schema_version": "grounding-v1"},
    )

    assert component.status is LookComponentStatus.PENDING
    assert component.item_id is None

    item_id = uuid4()
    ready = component.with_item(item_id)

    assert ready.status is LookComponentStatus.READY
    assert ready.item_id == item_id

    with pytest.raises(ValueError, match="ready component must reference an Item"):
        LookComponent(
            id=uuid4(),
            look_id=uuid4(),
            component_key="missing-item",
            status=LookComponentStatus.READY,
            item_id=None,
            evidence_region=component.evidence_region,
            role=None,
            layer=None,
            display_order=0,
            confidence=0.5,
            grounding_metadata={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    with pytest.raises(ValueError, match="non-ready component cannot reference an Item"):
        LookComponent(
            id=uuid4(),
            look_id=uuid4(),
            component_key="fake-pending",
            status=LookComponentStatus.PENDING,
            item_id=uuid4(),
            evidence_region=component.evidence_region,
            role=None,
            layer=None,
            display_order=0,
            confidence=0.5,
            grounding_metadata={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


def test_look_analysis_keeps_relationships_and_versioned_model_evidence() -> None:
    relation = LookAnalysisField(
        value="soft neutral layering",
        confidence=0.88,
    )
    analysis = LookAnalysis(
        color=relation,
        silhouette=relation,
        material=relation,
        layering=relation,
        focal_point=relation,
        scene=relation,
        style=relation,
        metadata=LookAnalysisMetadata(
            capability_alias="vision_understanding",
            model_version="look-model-v1",
            prompt_version="look-analysis-v1",
            schema_version="look-analysis-v1",
            taxonomy_version="stylecapture-v1",
            latency_ms=42,
        ),
    )
    look = Look.feed_saved(
        user_id=uuid4(),
        capture_id=uuid4(),
        source_selection_key="outfit",
    ).with_analysis(analysis)

    assert look.analysis == analysis
    assert look.analysis.layering.value == "soft neutral layering"
    assert look.analysis.metadata.prompt_version == "look-analysis-v1"
    assert look.analysis.metadata.schema_version == "look-analysis-v1"


def test_preference_signals_are_append_only_events_with_valid_payloads() -> None:
    user_id = uuid4()
    look_id = uuid4()
    saved = PreferenceSignal.look_saved(
        user_id=user_id,
        look_id=look_id,
        idempotency_key="capture-save:request-1",
    )
    reason = PreferenceSignal.liking_reason(
        user_id=user_id,
        look_id=look_id,
        reason="喜欢低饱和色彩和清晰的层次",
        idempotency_key="look-reason:request-2",
    )

    assert saved.kind is PreferenceSignalKind.LOOK_SAVED
    assert saved.payload == {}
    assert reason.kind is PreferenceSignalKind.LIKING_REASON_ADDED
    assert reason.payload == {"reason": "喜欢低饱和色彩和清晰的层次"}
    with pytest.raises(FrozenInstanceError):
        reason.payload = {"reason": "mutated"}  # type: ignore[misc]
    with pytest.raises(ValueError, match="liking reason must not be empty"):
        PreferenceSignal.liking_reason(
            user_id=user_id,
            look_id=look_id,
            reason=" ",
            idempotency_key="look-reason:request-3",
        )
