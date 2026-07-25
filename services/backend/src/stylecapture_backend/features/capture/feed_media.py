from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from stylecapture_backend.features.capture.domain import (
    FeedSelection,
    ImagePayload,
    NormalizedPoint,
)


@dataclass(frozen=True, slots=True)
class ExtractFrameRequest:
    source_object_key: str
    frame_object_key: str
    timestamp_ms: int

    def __post_init__(self) -> None:
        if not self.source_object_key.strip():
            raise ValueError("source object key must not be empty")
        if not self.frame_object_key.strip():
            raise ValueError("frame object key must not be empty")
        if not 0 <= self.timestamp_ms <= 86_400_000:
            raise ValueError("frame timestamp must be between 0 and 24 hours")


class SegmentationRepresentation(StrEnum):
    COARSE_POLYGON = "coarse_polygon"
    REFINED_MASK = "refined_mask"


@dataclass(frozen=True, slots=True)
class SegmentationPrompt:
    frame: ImagePayload
    selection: FeedSelection
    fallback_reason: str

    def __post_init__(self) -> None:
        if not self.fallback_reason.strip():
            raise ValueError("segmentation fallback reason must not be empty")


@dataclass(frozen=True, slots=True)
class SegmentationMetadata:
    provider: str
    representation: SegmentationRepresentation
    refined: bool
    schema_version: str
    latency_ms: int
    fallback_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("segmentation provider must not be empty")
        if not self.schema_version.strip():
            raise ValueError("segmentation schema version must not be empty")
        if self.latency_ms < 0:
            raise ValueError("segmentation latency must not be negative")
        if self.refined and self.representation is not SegmentationRepresentation.REFINED_MASK:
            raise ValueError("refined segmentation must use the refined-mask representation")
        if not self.refined and self.representation is not SegmentationRepresentation.COARSE_POLYGON:
            raise ValueError("unrefined segmentation must use the coarse-polygon representation")


@dataclass(frozen=True, slots=True)
class SegmentationResult:
    selection_key: str
    coarse_polygon: tuple[NormalizedPoint, ...]
    mask: ImagePayload | None
    metadata: SegmentationMetadata

    def __post_init__(self) -> None:
        if not self.selection_key.strip():
            raise ValueError("selection key must not be empty")
        if len(set(self.coarse_polygon)) < 3:
            raise ValueError("coarse polygon must contain at least 3 unique points")
        if self.metadata.refined and self.mask is None:
            raise ValueError("refined segmentation must include a mask")
        if not self.metadata.refined and self.mask is not None:
            raise ValueError("coarse segmentation must not claim a mask")


class FrameExtractor(Protocol):
    def extract(self, request: ExtractFrameRequest) -> ImagePayload: ...


class PromptableSegmentationPort(Protocol):
    def segment(self, prompt: SegmentationPrompt) -> SegmentationResult: ...
