from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
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
    error_code: str | None = None
    error_message: str | None = None

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

    def transition(
        self,
        target: JobState,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ProcessingJob:
        if target not in _ALLOWED_JOB_TRANSITIONS[self.state]:
            raise InvalidJobTransition(self.state, target)
        if target in {JobState.ERROR, JobState.PARTIAL}:
            if not error_code or not error_message:
                error_code = error_code or "processing_failed"
                error_message = error_message or "Processing did not complete"
        else:
            error_code = None
            error_message = None
        attempt = (
            self.attempt + 1
            if self.state is JobState.ERROR and target is JobState.QUEUED
            else self.attempt
        )
        return replace(
            self,
            state=target,
            attempt=attempt,
            error_code=error_code,
            error_message=error_message,
            updated_at=datetime.now(UTC),
        )
