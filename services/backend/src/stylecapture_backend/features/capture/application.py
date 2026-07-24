from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.ports import (
    CaptureRepository,
    CaptureSubmission,
    JobDispatcher,
    JobDispatchError,
    ObjectLookup,
)


class CaptureError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True, slots=True)
class SubmitCaptureCommand:
    user_id: UUID
    object_key: str
    sha256: str
    source_kind: CaptureSourceKind
    ownership: OwnershipState
    idempotency_key: str


class CaptureApplication:
    def __init__(
        self,
        *,
        captures: CaptureRepository,
        objects: ObjectLookup,
        dispatcher: JobDispatcher,
    ) -> None:
        self._captures = captures
        self._objects = objects
        self._dispatcher = dispatcher

    async def submit(self, command: SubmitCaptureCommand) -> CaptureSubmission:
        idempotency_key = command.idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise CaptureError(
                "invalid_idempotency_key",
                "Idempotency-Key must contain between 1 and 128 characters",
            )
        existing = await self._captures.find_by_idempotency(
            command.user_id,
            idempotency_key,
        )
        if existing is not None:
            self._dispatch(existing)
            return existing
        try:
            stored = self._objects.describe(command.object_key)
        except (KeyError, FileNotFoundError) as error:
            raise CaptureError(
                "upload_not_found",
                "The prepared upload does not exist",
                details={"object_key": command.object_key},
            ) from error
        if stored.sha256 != command.sha256:
            raise CaptureError(
                "source_hash_mismatch",
                "The submitted source hash does not match the uploaded object",
            )
        capture = Capture.create(
            user_id=command.user_id,
            source=CaptureSource(
                kind=command.source_kind,
                object_key=stored.object_key,
                sha256=stored.sha256,
            ),
            ownership=command.ownership,
        )
        job = ProcessingJob.queued(capture_id=capture.id)
        submission = await self._captures.save_submission(
            capture,
            job,
            idempotency_key,
        )
        self._dispatch(submission)
        return submission

    def _dispatch(self, submission: CaptureSubmission) -> None:
        try:
            self._dispatcher.enqueue_capture(
                submission.capture.id,
                submission.job.id,
            )
        except JobDispatchError as error:
            raise CaptureError(
                "processing_dispatch_unavailable",
                "The upload is safe, but processing could not start; retry this request",
                details={
                    "capture_id": str(submission.capture.id),
                    "job_id": str(submission.job.id),
                    "retryable": True,
                },
            ) from error
