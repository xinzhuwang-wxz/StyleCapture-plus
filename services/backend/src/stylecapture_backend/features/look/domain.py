from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID, uuid4

from stylecapture_backend.features.capture.domain import NormalizedPoint, is_valid_selection_key


class LookSource(StrEnum):
    FEED_SAVED = "feed_saved"
    USER_CREATED = "user_created"
    AI_GENERATED = "ai_generated"


class LookStatus(StrEnum):
    PROCESSING = "processing"
    PARTIAL = "partial"
    READY = "ready"
    ERROR = "error"


class LookComponentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class PreferenceSignalKind(StrEnum):
    LOOK_SAVED = "look_saved"
    LIKING_REASON_ADDED = "liking_reason_added"


@dataclass(frozen=True, slots=True)
class PreferenceSignal:
    id: UUID
    user_id: UUID
    look_id: UUID
    kind: PreferenceSignalKind
    payload: Mapping[str, object]
    idempotency_key: str
    created_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        normalized_key = self.idempotency_key.strip()
        if not 1 <= len(normalized_key) <= 128:
            raise ValueError("preference idempotency key must contain between 1 and 128 characters")
        object.__setattr__(self, "idempotency_key", normalized_key)
        if self.kind is PreferenceSignalKind.LOOK_SAVED and self.payload:
            raise ValueError("look-saved preference must not carry a payload")
        if self.kind is PreferenceSignalKind.LIKING_REASON_ADDED:
            reason = self.payload.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("liking reason must not be empty")
            if len(reason) > 1000:
                raise ValueError("liking reason must not exceed 1000 characters")
            if set(self.payload) != {"reason"}:
                raise ValueError("liking reason preference contains unsupported fields")

    @classmethod
    def look_saved(
        cls,
        *,
        user_id: UUID,
        look_id: UUID,
        idempotency_key: str,
    ) -> PreferenceSignal:
        return cls(
            id=uuid4(),
            user_id=user_id,
            look_id=look_id,
            kind=PreferenceSignalKind.LOOK_SAVED,
            payload={},
            idempotency_key=idempotency_key,
            created_at=datetime.now(UTC),
        )

    @classmethod
    def liking_reason(
        cls,
        *,
        user_id: UUID,
        look_id: UUID,
        reason: str,
        idempotency_key: str,
    ) -> PreferenceSignal:
        return cls(
            id=uuid4(),
            user_id=user_id,
            look_id=look_id,
            kind=PreferenceSignalKind.LIKING_REASON_ADDED,
            payload={"reason": reason.strip()},
            idempotency_key=idempotency_key,
            created_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class LookAnalysisField:
    value: str
    confidence: float

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("look analysis field value must not be empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("look analysis confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class LookAnalysisMetadata:
    capability_alias: str
    provider_model: str
    prompt_version: str
    schema_version: str
    taxonomy_version: str
    latency_ms: int

    def __post_init__(self) -> None:
        versioned_values = (
            self.capability_alias,
            self.provider_model,
            self.prompt_version,
            self.schema_version,
            self.taxonomy_version,
        )
        if any(not value.strip() for value in versioned_values):
            raise ValueError("look analysis model metadata must not be empty")
        if self.latency_ms < 0:
            raise ValueError("look analysis latency must not be negative")


@dataclass(frozen=True, slots=True)
class LookAnalysis:
    color: LookAnalysisField
    silhouette: LookAnalysisField
    material: LookAnalysisField
    layering: LookAnalysisField
    focal_point: LookAnalysisField
    scene: LookAnalysisField
    style: LookAnalysisField
    metadata: LookAnalysisMetadata


@dataclass(frozen=True, slots=True)
class LookComponent:
    id: UUID
    look_id: UUID
    component_key: str
    status: LookComponentStatus
    item_id: UUID | None
    evidence_region: tuple[NormalizedPoint, ...]
    role: str | None
    layer: str | None
    display_order: int
    confidence: float
    grounding_metadata: Mapping[str, object]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "grounding_metadata",
            MappingProxyType(dict(self.grounding_metadata)),
        )
        if not is_valid_selection_key(self.component_key):
            raise ValueError("component key must be a 1-64 character ASCII alphanumeric identifier")
        if len(set(self.evidence_region)) < 3:
            raise ValueError("component evidence region must contain at least 3 unique points")
        if not 0 <= self.confidence <= 1:
            raise ValueError("component confidence must be between 0 and 1")
        if self.display_order < 0:
            raise ValueError("component display order must not be negative")
        if self.status is LookComponentStatus.READY and self.item_id is None:
            raise ValueError("ready component must reference an Item")
        if self.status is not LookComponentStatus.READY and self.item_id is not None:
            raise ValueError("non-ready component cannot reference an Item")

    @classmethod
    def pending(
        cls,
        *,
        look_id: UUID,
        component_key: str,
        evidence_region: tuple[NormalizedPoint, ...],
        confidence: float,
        grounding_metadata: Mapping[str, object],
        role: str | None = None,
        layer: str | None = None,
        display_order: int = 0,
    ) -> LookComponent:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            look_id=look_id,
            component_key=component_key,
            status=LookComponentStatus.PENDING,
            item_id=None,
            evidence_region=evidence_region,
            role=role,
            layer=layer,
            display_order=display_order,
            confidence=confidence,
            grounding_metadata=grounding_metadata,
            created_at=now,
            updated_at=now,
        )

    def with_item(self, item_id: UUID) -> LookComponent:
        return replace(
            self,
            status=LookComponentStatus.READY,
            item_id=item_id,
            updated_at=datetime.now(UTC),
        )

    def with_status(self, status: LookComponentStatus) -> LookComponent:
        if status is LookComponentStatus.READY:
            raise ValueError("ready component status requires an Item")
        return replace(
            self,
            status=status,
            item_id=None,
            updated_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class Look:
    id: UUID
    user_id: UUID
    capture_id: UUID
    source_selection_key: str
    source: LookSource
    status: LookStatus
    analysis: LookAnalysis | None
    display_object_key: str | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not is_valid_selection_key(self.source_selection_key):
            raise ValueError(
                "source selection key must be a 1-64 character ASCII alphanumeric identifier"
            )
        if self.display_object_key is not None:
            normalized_key = self.display_object_key.strip()
            if not normalized_key or len(normalized_key) > 512:
                raise ValueError("display object key must contain between 1 and 512 characters")
            object.__setattr__(self, "display_object_key", normalized_key)

    @classmethod
    def feed_saved(
        cls,
        *,
        user_id: UUID,
        capture_id: UUID,
        source_selection_key: str,
    ) -> Look:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            capture_id=capture_id,
            source_selection_key=source_selection_key,
            source=LookSource.FEED_SAVED,
            status=LookStatus.PROCESSING,
            analysis=None,
            display_object_key=None,
            created_at=now,
            updated_at=now,
        )

    def with_analysis(self, analysis: LookAnalysis) -> Look:
        return replace(
            self,
            analysis=analysis,
            updated_at=datetime.now(UTC),
        )

    def with_display_object(self, object_key: str) -> Look:
        normalized_key = object_key.strip()
        if not normalized_key:
            raise ValueError("display object key must not be empty")
        return replace(
            self,
            display_object_key=normalized_key,
            updated_at=datetime.now(UTC),
        )

    def with_status(self, status: LookStatus) -> Look:
        return replace(
            self,
            status=status,
            updated_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class LookDetail:
    look: Look
    components: tuple[LookComponent, ...]
    preference_signals: tuple[PreferenceSignal, ...]

    def __post_init__(self) -> None:
        if any(component.look_id != self.look.id for component in self.components):
            raise ValueError("Look detail contains a component from another Look")
        if any(
            signal.look_id != self.look.id or signal.user_id != self.look.user_id
            for signal in self.preference_signals
        ):
            raise ValueError("Look detail contains a preference from another user or Look")
