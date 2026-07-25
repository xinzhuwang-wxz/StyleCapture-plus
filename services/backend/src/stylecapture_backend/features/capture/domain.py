from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from uuid import UUID, uuid4

from stylecapture_backend.platform.image_payload import ImagePayload as ImagePayload


class CaptureSourceKind(StrEnum):
    UPLOAD = "upload"
    CAMERA = "camera"
    FEED = "feed"


class CaptureIntent(StrEnum):
    ITEM = "item"
    WHOLE_OUTFIT = "whole_outfit"


@dataclass(frozen=True, slots=True)
class NormalizedPoint:
    x: float
    y: float

    def __post_init__(self) -> None:
        if (
            not isfinite(self.x)
            or not isfinite(self.y)
            or not 0 <= self.x <= 1
            or not 0 <= self.y <= 1
        ):
            raise ValueError("normalized point coordinates must be finite and between 0 and 1")


def is_valid_selection_key(value: str) -> bool:
    return (
        1 <= len(value) <= 64
        and value.isascii()
        and value[0].isalnum()
        and all(character.isalnum() or character in {"_", "-"} for character in value)
    )


@dataclass(frozen=True, slots=True)
class FeedSelection:
    selection_key: str
    polygon: tuple[NormalizedPoint, ...]

    def __post_init__(self) -> None:
        if not is_valid_selection_key(self.selection_key):
            raise ValueError("selection key must be a 1-64 character ASCII alphanumeric identifier")
        if len(set(self.polygon)) < 3:
            raise ValueError("selection polygon must contain at least 3 unique points")


class FeedCaptureIntent(StrEnum):
    ITEM_SELECTIONS = "item_selections"
    WHOLE_OUTFIT = "whole_outfit"


@dataclass(frozen=True, slots=True)
class FeedFrameContext:
    video_ref: str
    timestamp_ms: int
    frame_width: int
    frame_height: int
    selections: tuple[FeedSelection, ...]
    intent: FeedCaptureIntent = FeedCaptureIntent.ITEM_SELECTIONS

    def __post_init__(self) -> None:
        if not 1 <= len(self.selections) <= 8:
            raise ValueError("a feed frame must contain between 1 and 8 selections")
        if self.intent is FeedCaptureIntent.WHOLE_OUTFIT and len(self.selections) != 1:
            raise ValueError("a whole-outfit Feed capture must contain exactly one selection")
        selection_keys = [selection.selection_key for selection in self.selections]
        if len(selection_keys) != len(set(selection_keys)):
            raise ValueError("selection keys must be unique within a feed frame")


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
    feed_context: FeedFrameContext | None = None
    intent: CaptureIntent = CaptureIntent.ITEM

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        source: CaptureSource,
        ownership: OwnershipState,
        feed_context: FeedFrameContext | None = None,
        intent: CaptureIntent = CaptureIntent.ITEM,
    ) -> Capture:
        return cls(
            id=uuid4(),
            user_id=user_id,
            source=source,
            ownership=ownership,
            created_at=datetime.now(UTC),
            feed_context=feed_context,
            intent=intent,
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
