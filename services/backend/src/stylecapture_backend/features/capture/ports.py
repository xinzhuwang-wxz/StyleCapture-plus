from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import BinaryIO, Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import Capture, ProcessingJob

CAPTURE_TASK_NAME = "stylecapture.capture.process"


@dataclass(frozen=True, slots=True)
class UploadRequest:
    owner_id: UUID
    file_name: str
    content_type: str
    byte_size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class PreparedUpload:
    upload_url: str
    object_key: str
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class StoredObject:
    owner_id: UUID | None
    object_key: str
    content_type: str
    byte_size: int
    sha256: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class CaptureSubmission:
    capture: Capture
    job: ProcessingJob
    look_id: UUID | None = None


class LookIdentity(Protocol):
    @property
    def id(self) -> UUID: ...


class WholeOutfitRegistrar(Protocol):
    async def ensure_saved_look(
        self,
        capture: Capture,
        *,
        idempotency_key: str,
    ) -> LookIdentity: ...


class JobDispatchError(RuntimeError):
    """The durable job exists, but the broker did not accept its task."""


class ObjectStore(Protocol):
    def prepare_upload(
        self,
        request: UploadRequest,
        *,
        ttl: timedelta = timedelta(minutes=10),
    ) -> PreparedUpload: ...

    def accept_upload(
        self,
        token: str,
        *,
        body: bytes,
        content_type: str,
    ) -> StoredObject: ...

    def describe(self, object_key: str) -> StoredObject: ...

    def read(self, object_key: str) -> bytes: ...

    def delete(self, object_key: str) -> None: ...

    def mark_attached(self, object_key: str, owner_id: UUID) -> None: ...

    def discard_unattached_upload(self, object_key: str, owner_id: UUID) -> None: ...


class ObjectLookup(Protocol):
    def describe(self, object_key: str) -> StoredObject: ...


class CaptureRepository(Protocol):
    async def find_by_idempotency(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> CaptureSubmission | None: ...

    async def save_submission(
        self,
        capture: Capture,
        job: ProcessingJob,
        idempotency_key: str,
    ) -> CaptureSubmission: ...


class JobDispatcher(Protocol):
    def enqueue_capture(self, capture_id: UUID, job_id: UUID) -> None: ...


class JobRepository(Protocol):
    async def get_for_user(self, job_id: UUID, user_id: UUID) -> ProcessingJob | None: ...

    async def get_by_capture_for_user(
        self,
        capture_id: UUID,
        user_id: UUID,
    ) -> ProcessingJob | None: ...

    async def update(self, job: ProcessingJob) -> ProcessingJob: ...


class BinaryObjectReader(Protocol):
    def open(self, object_key: str) -> BinaryIO: ...
