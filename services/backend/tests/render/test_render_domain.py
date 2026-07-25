from dataclasses import replace
from uuid import uuid4

import pytest
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderInputSignature,
    RenderOutput,
    RenderPrivacy,
)


def signature() -> RenderInputSignature:
    return RenderInputSignature(version="look-render-v1", hash="a" * 64)


def output() -> RenderOutput:
    return RenderOutput(
        object_key="derived/renders/look.webp",
        content_hash="b" * 64,
        content_type="image/webp",
    )


def test_only_pixel_cover_artifacts_can_be_share_eligible() -> None:
    user_id = uuid4()
    look_id = uuid4()

    with pytest.raises(ValueError, match="only pixel cover"):
        RenderArtifact.queued(
            user_id=user_id,
            look_id=look_id,
            kind=RenderArtifactKind.COLLAGE,
            input_signature=signature(),
            request_key="collage-request",
            privacy=RenderPrivacy.SHAREABLE_PIXEL,
        )

    pixel = RenderArtifact.queued(
        user_id=user_id,
        look_id=look_id,
        kind=RenderArtifactKind.PIXEL_COVER,
        input_signature=signature(),
        request_key="pixel-request",
        privacy=RenderPrivacy.SHAREABLE_PIXEL,
    ).mark_succeeded(output())

    assert pixel.share_eligible is True


def test_try_on_degradation_references_the_real_collage_fallback_without_success() -> None:
    user_id = uuid4()
    look_id = uuid4()
    collage = RenderArtifact.queued(
        user_id=user_id,
        look_id=look_id,
        kind=RenderArtifactKind.COLLAGE,
        input_signature=signature(),
        request_key="collage-request",
    ).mark_succeeded(output())
    try_on = RenderArtifact.queued(
        user_id=user_id,
        look_id=look_id,
        kind=RenderArtifactKind.TRY_ON,
        input_signature=signature(),
        request_key="try-on-request",
    )

    degraded = try_on.mark_degraded_to(
        fallback=collage,
        reason="hosted try-on timeout; showing deterministic collage",
    )

    assert degraded.status == "degraded"
    assert degraded.output == collage.output
    assert degraded.fallback_artifact_id == collage.id
    assert degraded.failure_message == "hosted try-on timeout; showing deterministic collage"


def test_non_terminal_artifacts_cannot_claim_output() -> None:
    queued = RenderArtifact.queued(
        user_id=uuid4(),
        look_id=uuid4(),
        kind=RenderArtifactKind.COLLAGE,
        input_signature=signature(),
        request_key="collage-request",
    )

    with pytest.raises(ValueError, match="cannot reference output"):
        replace(queued, output=output())
