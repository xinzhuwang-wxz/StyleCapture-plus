from dataclasses import replace
from uuid import uuid4

from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    OwnershipState,
)
from stylecapture_backend.features.look.domain import (
    COMPOSITION_ITEM_EVIDENCE,
    Look,
    LookAnalysis,
    LookAnalysisField,
    LookAnalysisMetadata,
    LookComponent,
    LookDetail,
)
from stylecapture_backend.features.render.application import RenderArtifactView
from stylecapture_backend.features.render.domain import RenderArtifactKind, RenderArtifactStatus
from stylecapture_backend.features.render.signatures import (
    RENDER_PIPELINE_VERSIONS,
    build_render_input_signature,
)


def test_dependent_render_signature_does_not_change_when_source_finishes() -> None:
    user_id = uuid4()
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.UPLOAD,
            object_key="originals/upload/look.jpg",
            sha256="a" * 64,
        ),
        ownership=OwnershipState.OWNED,
    )
    look = Look.user_created(
        user_id=user_id,
        capture_id=capture.id,
        source_selection_key="whole_outfit",
    )
    detail = LookDetail(look=look, components=(), preference_signals=())
    source = RenderArtifactView(
        id=uuid4(),
        user_id=user_id,
        look_id=look.id,
        kind=RenderArtifactKind.COLLAGE,
        status=RenderArtifactStatus.QUEUED,
        input_version="look-render-v1",
        input_hash="b" * 64,
        request_key="collage",
        object_key=None,
        content_hash=None,
        content_type=None,
        sprite_object_key=None,
        sprite_content_hash=None,
        sprite_content_type=None,
        source_artifact_id=None,
        fallback_artifact_id=None,
        failure_code=None,
        failure_message=None,
        share_eligible=False,
        created_at=look.created_at,
        updated_at=look.updated_at,
        subject_object_key=None,
        subject_used=False,
        sprite_extraction_failed=False,
    )

    queued_signature = build_render_input_signature(
        detail,
        capture,
        RenderArtifactKind.PIXEL_COVER,
        source_artifact=source,
    )
    completed_signature = build_render_input_signature(
        detail,
        capture,
        RenderArtifactKind.PIXEL_COVER,
        source_artifact=replace(
            source,
            status=RenderArtifactStatus.SUCCEEDED,
            object_key="derived/renders/collage.png",
            content_hash="c" * 64,
            content_type="image/png",
        ),
    )

    assert completed_signature == queued_signature


def test_try_on_signature_uses_audited_doubao_skill_pipeline_version() -> None:
    assert RENDER_PIPELINE_VERSIONS[RenderArtifactKind.TRY_ON] == (
        "doubao-virtual-try-on-skill-v1.4.1"
    )


def test_composition_signature_uses_item_versions_not_an_unrelated_capture() -> None:
    user_id = uuid4()
    field = LookAnalysisField(value="通勤", confidence=0.9)
    look = Look.ai_generated(
        user_id=user_id,
        source_selection_key="ai123",
        analysis=LookAnalysis(
            color=field,
            silhouette=field,
            material=field,
            layering=field,
            focal_point=field,
            scene=field,
            style=field,
            metadata=LookAnalysisMetadata(
                capability_alias="reasoning",
                model_version="test",
                prompt_version="v1",
                schema_version="v1",
                taxonomy_version="v1",
                latency_ms=1,
            ),
        ),
    )
    item_id = uuid4()
    component = LookComponent.pending(
        look_id=look.id,
        component_key="slot1",
        evidence_region=(),
        confidence=0,
        grounding_metadata={
            "evidence_type": COMPOSITION_ITEM_EVIDENCE,
            "item_capture_id": str(uuid4()),
            "item_selection_key": "top1",
            "item_source_object_key": "originals/top.png",
            "item_display_object_key": "derived/top.png",
            "item_version": "2026-07-26T00:00:00+00:00",
        },
    ).with_item(item_id)
    detail = LookDetail(look=look, components=(component,), preference_signals=())

    original = build_render_input_signature(
        detail,
        None,
        RenderArtifactKind.COLLAGE,
    )
    changed_item_version = build_render_input_signature(
        LookDetail(
            look=look,
            components=(
                replace(
                    component,
                    grounding_metadata={
                        **component.grounding_metadata,
                        "item_version": "2026-07-26T00:01:00+00:00",
                    },
                ),
            ),
            preference_signals=(),
        ),
        None,
        RenderArtifactKind.COLLAGE,
    )
    changed_display = build_render_input_signature(
        detail,
        None,
        RenderArtifactKind.COLLAGE,
        look_display_hash="f" * 64,
    )

    assert (
        RENDER_PIPELINE_VERSIONS[RenderArtifactKind.COLLAGE] == "collage-v6-centered-square-cutout"
    )
    assert original != changed_item_version
    assert original != changed_display
