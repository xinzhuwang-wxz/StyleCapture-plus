from __future__ import annotations

import json
from hashlib import sha256

from stylecapture_backend.features.capture.domain import Capture
from stylecapture_backend.features.look.domain import LookDetail
from stylecapture_backend.features.render.application import RenderArtifactView
from stylecapture_backend.features.render.domain import RenderArtifactKind, RenderInputSignature
from stylecapture_backend.features.render.prompt_contracts import (
    PIXEL_COVER_PROMPT_VERSION,
    TRY_ON_PROMPT_VERSION,
)

RENDER_PIPELINE_VERSIONS = {
    RenderArtifactKind.COLLAGE: "collage-v3-flat-lay-hero",
    RenderArtifactKind.TRY_ON: TRY_ON_PROMPT_VERSION,
    RenderArtifactKind.PIXEL_COVER: PIXEL_COVER_PROMPT_VERSION,
}


def build_render_input_signature(
    detail: LookDetail,
    capture: Capture | None,
    kind: RenderArtifactKind,
    *,
    source_artifact: RenderArtifactView | None = None,
    subject_source_hash: str | None = None,
    look_display_hash: str | None = None,
) -> RenderInputSignature:
    payload = {
        "source_provenance": (
            {
                "kind": "capture",
                "capture_id": str(capture.id),
                "source_hash": capture.source.sha256,
            }
            if capture is not None
            else {
                "kind": "composition",
                "items": [
                    {
                        "item_id": str(component.item_id),
                        "item_capture_id": component.grounding_metadata.get("item_capture_id"),
                        "item_selection_key": component.grounding_metadata.get(
                            "item_selection_key"
                        ),
                        "item_source_object_key": component.grounding_metadata.get(
                            "item_source_object_key"
                        ),
                        "item_display_object_key": component.grounding_metadata.get(
                            "item_display_object_key"
                        ),
                        "item_version": component.grounding_metadata.get("item_version"),
                    }
                    for component in detail.components
                    if component.item_id is not None
                ],
            }
        ),
        "components": [
            {
                "component_key": component.component_key,
                "display_order": component.display_order,
                "item_id": str(component.item_id) if component.item_id is not None else None,
                "role": component.role,
                "status": component.status.value,
            }
            for component in detail.components
        ],
        "display_object_key": detail.look.display_object_key,
        "look_display_hash": look_display_hash,
        "look_id": str(detail.look.id),
        "kind": kind.value,
        "pipeline_version": RENDER_PIPELINE_VERSIONS[kind],
        "look_status": detail.look.status.value,
        "look_updated_at": detail.look.updated_at.isoformat(),
        "source_artifact": (
            {
                "id": str(source_artifact.id),
                "input_hash": source_artifact.input_hash,
            }
            if source_artifact is not None
            else None
        ),
        "subject_source_hash": subject_source_hash,
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return RenderInputSignature(
        version="look-render-v2",
        hash=sha256(encoded.encode("utf-8")).hexdigest(),
    )


def derived_render_request_key(
    request_key: str,
    kind: RenderArtifactKind,
) -> str:
    digest = sha256(request_key.encode("utf-8")).hexdigest()
    return f"auto-{kind.value}:{digest}"
