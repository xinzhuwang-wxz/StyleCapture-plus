from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID, uuid4


class OutfitCategory(StrEnum):
    TOP = "tops"
    BOTTOM = "bottoms"
    DRESS = "dresses"
    OUTERWEAR = "outerwear"
    SHOES = "shoes"
    ACCESSORY = "accessories"


@dataclass(frozen=True, slots=True)
class OutfitRequest:
    scene: str
    style: str | None = None
    weather: str | None = None
    comfort: str | None = None
    anchor_item_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.scene.strip():
            raise ValueError("scene must not be empty")


@dataclass(frozen=True, slots=True)
class OutfitSlot:
    role: OutfitCategory
    item_id: UUID | None
    item_name: str | None
    ownership: str | None
    image_url: str | None
    search_query: str | None

    def __post_init__(self) -> None:
        if (self.item_id is None) == (self.search_query is None):
            raise ValueError("slot must contain either a wardrobe item or a search demand")


@dataclass(frozen=True, slots=True)
class OutfitPlan:
    id: UUID
    title: str
    scene: str
    slots: tuple[OutfitSlot, ...]
    rationale: str
    style_match_score: int

    def __post_init__(self) -> None:
        if not 0 <= self.style_match_score <= 100:
            raise ValueError("style match score must be between 0 and 100")
        if len(self.slots) < 3:
            raise ValueError("an outfit plan must contain at least three slots")

    @property
    def missing_count(self) -> int:
        return sum(slot.item_id is None for slot in self.slots)

    @property
    def wardrobe_item_ids(self) -> tuple[UUID, ...]:
        return tuple(slot.item_id for slot in self.slots if slot.item_id is not None)

    def with_ranking(self, *, rationale: str, score: int) -> OutfitPlan:
        return replace(self, rationale=rationale.strip(), style_match_score=score)


@dataclass(frozen=True, slots=True)
class OutfitPlanSet:
    request_id: UUID
    plans: tuple[OutfitPlan, ...]
    degraded: bool
    degradation_reason: str | None
    explanation_state: str

    @classmethod
    def rule_ranked(
        cls,
        plans: tuple[OutfitPlan, ...],
        *,
        degradation_reason: str,
    ) -> OutfitPlanSet:
        return cls(
            request_id=uuid4(),
            plans=plans,
            degraded=True,
            degradation_reason=degradation_reason,
            explanation_state="rule_ranked",
        )
