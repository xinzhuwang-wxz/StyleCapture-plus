from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID, uuid4


class CaptureSourceKind(StrEnum):
    UPLOAD = "upload"
    CAMERA = "camera"
    FEED = "feed"


class OwnershipState(StrEnum):
    OWNED = "owned"
    INSPIRATION = "inspiration"


class JobState(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    PARTIAL = "partial"
    READY = "ready"
    ERROR = "error"


class FieldProvenance(StrEnum):
    MODEL = "model"
    USER = "user"
    CURATED_SEED = "curated_seed"


@dataclass(frozen=True, slots=True)
class CaptureSource:
    kind: CaptureSourceKind
    object_key: str
    sha256: str
    origin_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.object_key.strip():
            raise ValueError("object_key must not be empty")
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.sha256
        ):
            raise ValueError("sha256 must be a lowercase hexadecimal digest")


@dataclass(frozen=True, slots=True)
class Capture:
    id: UUID
    user_id: UUID
    source: CaptureSource
    ownership: OwnershipState
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        source: CaptureSource,
        ownership: OwnershipState,
    ) -> Capture:
        return cls(
            id=uuid4(),
            user_id=user_id,
            source=source,
            ownership=ownership,
            created_at=datetime.now(UTC),
        )


class InvalidJobTransition(ValueError):
    def __init__(self, current: JobState, target: JobState) -> None:
        super().__init__(f"cannot transition processing job from {current} to {target}")
        self.current = current
        self.target = target


_ALLOWED_JOB_TRANSITIONS: Mapping[JobState, frozenset[JobState]] = {
    JobState.QUEUED: frozenset({JobState.PROCESSING}),
    JobState.PROCESSING: frozenset({JobState.PARTIAL, JobState.READY, JobState.ERROR}),
    JobState.PARTIAL: frozenset({JobState.PROCESSING}),
    JobState.READY: frozenset(),
    JobState.ERROR: frozenset({JobState.QUEUED}),
}


@dataclass(frozen=True, slots=True)
class ProcessingJob:
    id: UUID
    capture_id: UUID
    state: JobState
    attempt: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def queued(cls, *, capture_id: UUID) -> ProcessingJob:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            capture_id=capture_id,
            state=JobState.QUEUED,
            attempt=1,
            created_at=now,
            updated_at=now,
        )

    def transition(self, target: JobState) -> ProcessingJob:
        if target not in _ALLOWED_JOB_TRANSITIONS[self.state]:
            raise InvalidJobTransition(self.state, target)
        attempt = (
            self.attempt + 1
            if self.state is JobState.ERROR and target is JobState.QUEUED
            else self.attempt
        )
        return replace(self, state=target, attempt=attempt, updated_at=datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class FieldEnvelope:
    value: object
    provenance: FieldProvenance
    confidence: float
    model_version: str | None
    locked: bool

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.provenance is FieldProvenance.USER and not self.locked:
            raise ValueError("user-provided fields must be locked")


@dataclass(frozen=True, slots=True)
class ModelField:
    value: object
    confidence: float
    model_version: str

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.model_version.strip():
            raise ValueError("model_version must not be empty")


@dataclass(frozen=True, slots=True)
class ItemAttributes:
    fields: Mapping[str, FieldEnvelope] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))

    def merge_model(self, incoming: Mapping[str, ModelField]) -> ItemAttributes:
        merged = dict(self.fields)
        for name, model_field in incoming.items():
            current = merged.get(name)
            if current is not None and current.locked:
                continue
            merged[name] = FieldEnvelope(
                value=model_field.value,
                provenance=FieldProvenance.MODEL,
                confidence=model_field.confidence,
                model_version=model_field.model_version,
                locked=False,
            )
        return ItemAttributes(fields=merged)
