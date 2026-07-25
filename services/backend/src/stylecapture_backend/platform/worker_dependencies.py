from __future__ import annotations

from stylecapture_backend.features.capture.feed_media import PromptableSegmentationPort
from stylecapture_backend.features.capture.infrastructure.feed_media import (
    CoarsePolygonSegmentationProvider,
    Sam2PromptableSegmentationProvider,
)
from stylecapture_backend.platform.config import BackendSettings


def build_promptable_segmenter(settings: BackendSettings) -> PromptableSegmentationPort:
    if settings.segmentation_mode == "coarse":
        return CoarsePolygonSegmentationProvider()
    return Sam2PromptableSegmentationProvider(
        model=settings.segmentation_model,
        model_alias=settings.segmentation_model_alias,
        device=settings.segmentation_device,
        score_threshold=settings.segmentation_score_threshold,
    )
