from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
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
class OutfitRecallRequirements:
    scene: str
    weather: str | None
    formality: str | None
    season: str | None
    exclude_item_ids: tuple[UUID, ...]
    required_roles: tuple[OutfitCategory, ...]
    anchor_item_id: UUID | None = None

    def __post_init__(self) -> None:
        if not self.scene.strip():
            raise ValueError("recall scene must not be empty")
        if not self.required_roles:
            raise ValueError("recall must request at least one outfit role")
        if len(set(self.required_roles)) != len(self.required_roles):
            raise ValueError("recall roles must be unique")
        if len(set(self.exclude_item_ids)) != len(self.exclude_item_ids):
            raise ValueError("recall exclusions must be unique")
        if self.anchor_item_id in self.exclude_item_ids:
            raise ValueError("recall anchor cannot be excluded")


@dataclass(frozen=True, slots=True)
class OutfitRequest:
    scene: str
    style: str | None = None
    weather: str | None = None
    formality: str | None = None
    comfort: str | None = None
    anchor_item_id: UUID | None = None
    must_include_item_ids: tuple[UUID, ...] = ()
    exclude_item_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        if not self.scene.strip():
            raise ValueError("scene must not be empty")
        if len(set(self.must_include_item_ids)) != len(self.must_include_item_ids):
            raise ValueError("must-include item ids must be unique")
        if len(set(self.exclude_item_ids)) != len(self.exclude_item_ids):
            raise ValueError("excluded item ids must be unique")
        if set(self.must_include_item_ids) & set(self.exclude_item_ids):
            raise ValueError("an item cannot be both required and excluded")
        if self.anchor_item_id in self.exclude_item_ids:
            raise ValueError("the anchor item cannot be excluded")

    @property
    def required_item_ids(self) -> tuple[UUID, ...]:
        if self.anchor_item_id is None or self.anchor_item_id in self.must_include_item_ids:
            return self.must_include_item_ids
        return (*self.must_include_item_ids, self.anchor_item_id)


@dataclass(frozen=True, slots=True)
class OutfitSlot:
    role: OutfitCategory
    item_id: UUID | None
    item_name: str | None
    ownership: str | None
    image_url: str | None
    search_query: str | None
    source_kind: str | None = None

    def __post_init__(self) -> None:
        if (self.item_id is None) == (self.search_query is None):
            raise ValueError("slot must contain either a wardrobe item or a search demand")

    @property
    def purchase_item_id(self) -> UUID | None:
        """Return the real inspiration asset that a purchase can promote."""

        if self.item_id is not None and self.ownership == "inspiration":
            return self.item_id
        return None

    @property
    def purchase_search_query(self) -> str | None:
        if self.search_query is not None:
            return self.search_query
        if self.purchase_item_id is not None:
            return self.item_name or self.role.value
        return None


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

    @property
    def structure_signature(self) -> tuple[str, ...]:
        return tuple(
            f"{slot.role.value}:{slot.item_id if slot.item_id is not None else 'missing'}"
            for slot in self.slots
        )

    def with_ranking(self, *, rationale: str, score: int) -> OutfitPlan:
        return replace(self, rationale=rationale.strip(), style_match_score=score)


@dataclass(frozen=True, slots=True)
class OutfitReasoningTrace:
    capability_alias: str
    model_version: str
    prompt_version: str
    schema_version: str
    latency_ms: int

    def __post_init__(self) -> None:
        for name in (
            "capability_alias",
            "model_version",
            "prompt_version",
            "schema_version",
        ):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must not be empty")
            object.__setattr__(self, name, value)
        if self.latency_ms < 0:
            raise ValueError("latency_ms must not be negative")


@dataclass(frozen=True, slots=True)
class OutfitRerankResult:
    plans: tuple[OutfitPlan, ...]
    trace: OutfitReasoningTrace


class OutfitWorkflowStatus(StrEnum):
    CANDIDATES_READY = "candidates_ready"
    COMPLETED = "completed"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class OutfitWorkflowTrace:
    id: UUID
    user_id: UUID
    request_id: UUID
    status: OutfitWorkflowStatus
    explanation_state: str
    plan_count: int
    capability_alias: str
    model_version: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.plan_count < 1:
            raise ValueError("workflow trace must describe at least one plan")
        for name in ("explanation_state", "capability_alias", "model_version"):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} must not be empty")
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class OutfitPlanSet:
    request_id: UUID
    plans: tuple[OutfitPlan, ...]
    degraded: bool
    degradation_reason: str | None
    explanation_state: str
    reasoning_trace: OutfitReasoningTrace | None = None

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


class PurchaseDemandStatus(StrEnum):
    WANTED = "wanted"
    PURCHASED_PENDING = "purchased_pending"
    OWNED = "owned"


@dataclass(frozen=True, slots=True)
class PurchaseDemand:
    id: UUID
    user_id: UUID
    look_id: UUID
    role: OutfitCategory
    search_query: str
    status: PurchaseDemandStatus
    item_id: UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def wanted(
        cls,
        *,
        id: UUID,
        user_id: UUID,
        look_id: UUID,
        role: OutfitCategory,
        search_query: str,
        item_id: UUID | None = None,
    ) -> PurchaseDemand:
        if not search_query.strip():
            raise ValueError("purchase search query must not be empty")
        now = datetime.now(UTC)
        return cls(
            id=id,
            user_id=user_id,
            look_id=look_id,
            role=role,
            search_query=search_query.strip(),
            status=PurchaseDemandStatus.WANTED,
            item_id=item_id,
            created_at=now,
            updated_at=now,
        )

    def advance(self, target: PurchaseDemandStatus) -> PurchaseDemand:
        allowed = {
            PurchaseDemandStatus.WANTED: PurchaseDemandStatus.PURCHASED_PENDING,
            PurchaseDemandStatus.PURCHASED_PENDING: PurchaseDemandStatus.OWNED,
        }
        if target is self.status:
            return self
        if target is PurchaseDemandStatus.OWNED and self.item_id is None:
            raise ValueError("purchase demand requires a linked wardrobe item before ownership")
        if allowed.get(self.status) is not target:
            raise ValueError("purchase demand status must advance in order")
        return replace(self, status=target, updated_at=datetime.now(UTC))

    @property
    def can_mark_owned(self) -> bool:
        return self.item_id is not None
