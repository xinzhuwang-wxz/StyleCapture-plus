from __future__ import annotations

from stylecapture_backend.features.capture.feed_media import PromptableSegmentationPort
from stylecapture_backend.features.capture.infrastructure.feed_media import (
    CoarsePolygonSegmentationProvider,
    Sam2PromptableSegmentationProvider,
)
from stylecapture_backend.features.look.infrastructure.outfit_analysis import (
    CompletionCall,
    LiteLLMOutfitAnalyzer,
)
from stylecapture_backend.platform.config import BackendSettings


def build_outfit_analyzer(
    settings: BackendSettings,
    *,
    completion: CompletionCall | None = None,
) -> LiteLLMOutfitAnalyzer:
    if completion is None:
        return LiteLLMOutfitAnalyzer(
            capability_alias=settings.outfit_analysis_model_alias,
            fallback_alias=settings.outfit_analysis_fallback_model_alias,
            gateway_base_url=settings.litellm_base_url,
            gateway_api_key=settings.litellm_api_key.get_secret_value(),
        )
    return LiteLLMOutfitAnalyzer(
        capability_alias=settings.outfit_analysis_model_alias,
        fallback_alias=settings.outfit_analysis_fallback_model_alias,
        gateway_base_url=settings.litellm_base_url,
        gateway_api_key=settings.litellm_api_key.get_secret_value(),
        completion=completion,
    )


def build_promptable_segmenter(settings: BackendSettings) -> PromptableSegmentationPort:
    if settings.segmentation_mode == "coarse":
        return CoarsePolygonSegmentationProvider()
    return Sam2PromptableSegmentationProvider(
        model=settings.segmentation_model,
        model_alias=settings.segmentation_model_alias,
        device=settings.segmentation_device,
        score_threshold=settings.segmentation_score_threshold,
    )
