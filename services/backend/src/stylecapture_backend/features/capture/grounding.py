from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from stylecapture_backend.features.capture.domain import FeedSelection, ImagePayload
from stylecapture_backend.features.capture.processing import ModelMetadata
from stylecapture_backend.features.wardrobe.taxonomy import GarmentCategory

ARK_COORDINATE_MAX = 999


@dataclass(frozen=True, slots=True)
class NormalizedBox:
    """Ark visual-grounding coordinates in the documented 0..999 space."""

    x_min: int
    y_min: int
    x_max: int
    y_max: int

    def __post_init__(self) -> None:
        coordinates = (self.x_min, self.y_min, self.x_max, self.y_max)
        if any(value < 0 or value > ARK_COORDINATE_MAX for value in coordinates):
            raise ValueError("grounding coordinates must be between 0 and 999")
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("grounding box must have positive area")


@dataclass(frozen=True, slots=True)
class GroundingCandidate:
    label: str
    category: GarmentCategory
    box: NormalizedBox
    confidence: float
    visible_fraction: float

    def __post_init__(self) -> None:
        if not self.label or len(self.label) > 80:
            raise ValueError("grounding label must contain between 1 and 80 characters")
        if not self.label.replace("_", "").isalnum() or self.label.lower() != self.label:
            raise ValueError("grounding label must be a lowercase stable ID")
        if not 0 <= self.confidence <= 1:
            raise ValueError("grounding confidence must be between 0 and 1")
        if not 0 <= self.visible_fraction <= 1:
            raise ValueError("visible fraction must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class GroundingAnalysis:
    candidates: tuple[GroundingCandidate, ...]
    metadata: ModelMetadata

    def __post_init__(self) -> None:
        if not self.candidates:
            raise ValueError("grounding analysis must contain candidates")
        labels = [candidate.label for candidate in self.candidates]
        if len(labels) != len(set(labels)):
            raise ValueError("grounding candidate labels must be unique")


class VisualGroundingPort(Protocol):
    async def ground(
        self,
        image: ImagePayload,
        *,
        scope: FeedSelection,
    ) -> GroundingAnalysis: ...
