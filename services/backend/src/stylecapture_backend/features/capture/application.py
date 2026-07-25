from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import UUID

from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureIntent,
    CaptureSource,
    CaptureSourceKind,
    FeedCaptureIntent,
    FeedFrameContext,
    JobState,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.ports import (
    CaptureRepository,
    CaptureSubmission,
    JobDispatcher,
    JobDispatchError,
    JobRepository,
    ObjectLookup,
    WholeOutfitRegistrar,
)
from stylecapture_backend.features.look.ports import LookPersistenceUnavailable


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
    feed_context: FeedFrameContext | None = None
    intent: CaptureIntent = CaptureIntent.ITEM


class CaptureApplication:
    def __init__(
        self,
        *,
        captures: CaptureRepository,
        objects: ObjectLookup,
        dispatcher: JobDispatcher,
        whole_outfits: WholeOutfitRegistrar | None = None,
    ) -> None:
        self._captures = captures
        self._objects = objects
        self._dispatcher = dispatcher
        self._whole_outfits = whole_outfits

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
            existing = await self._ensure_whole_outfit(existing, idempotency_key)
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
        if stored.owner_id != command.user_id:
            raise CaptureError(
                "upload_not_found",
                "The prepared upload does not exist",
            )
        if stored.sha256 != command.sha256:
            raise CaptureError(
                "source_hash_mismatch",
                "The submitted source hash does not match the uploaded object",
            )
        if command.source_kind is CaptureSourceKind.FEED:
            if command.feed_context is None:
                raise CaptureError(
                    "feed_context_required",
                    "Feed captures require frame and selection context",
                )
            if (
                stored.width != command.feed_context.frame_width
                or stored.height != command.feed_context.frame_height
            ):
                raise CaptureError(
                    "feed_frame_dimensions_mismatch",
                    "Feed frame dimensions do not match the uploaded frame",
                )
        capture = Capture.create(
            user_id=command.user_id,
            source=CaptureSource(
                kind=command.source_kind,
                object_key=stored.object_key,
                sha256=stored.sha256,
                origin_ref=(
                    command.feed_context.video_ref if command.feed_context is not None else None
                ),
            ),
            ownership=command.ownership,
            feed_context=command.feed_context,
            intent=command.intent,
        )
        job = ProcessingJob.queued(capture_id=capture.id)
        submission = await self._captures.save_submission(
            capture,
            job,
            idempotency_key,
        )
        submission = await self._ensure_whole_outfit(submission, idempotency_key)
        self._dispatch(submission)
        return submission

    async def _ensure_whole_outfit(
        self,
        submission: CaptureSubmission,
        idempotency_key: str,
    ) -> CaptureSubmission:
        capture = submission.capture
        context = capture.feed_context
        is_whole_outfit = capture.intent is CaptureIntent.WHOLE_OUTFIT or (
            context is not None and context.intent is FeedCaptureIntent.WHOLE_OUTFIT
        )
        if not is_whole_outfit:
            return submission
        if self._whole_outfits is None:
            raise CaptureError(
                "look_registration_unavailable",
                "The outfit frame is safe, but its Look could not be registered; retry this request",
                details={
                    "capture_id": str(submission.capture.id),
                    "job_id": str(submission.job.id),
                    "retryable": True,
                },
            )
        try:
            look = await self._whole_outfits.ensure_saved_look(
                submission.capture,
                idempotency_key=idempotency_key,
            )
        except LookPersistenceUnavailable as error:
            raise CaptureError(
                "look_registration_unavailable",
                "The outfit frame is safe, but its Look could not be registered; retry this request",
                details={
                    "capture_id": str(submission.capture.id),
                    "job_id": str(submission.job.id),
                    "retryable": True,
                },
            ) from error
        return replace(submission, look_id=look.id)

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


class JobRetryApplication:
    def __init__(
        self,
        *,
        jobs: JobRepository,
        dispatcher: JobDispatcher,
    ) -> None:
        self._jobs = jobs
        self._dispatcher = dispatcher

    async def retry(self, user_id: UUID, job_id: UUID) -> ProcessingJob:
        job = await self._jobs.get_for_user(job_id, user_id)
        if job is None:
            raise CaptureError("job_not_found", "The processing job does not exist")
        if job.state in {JobState.PROCESSING, JobState.READY}:
            raise CaptureError(
                "job_not_retryable",
                "Only queued, partial, or failed jobs can be retried",
            )
        if job.state is JobState.ERROR:
            job = await self._jobs.update(job.transition(JobState.QUEUED))
        try:
            self._dispatcher.enqueue_capture(job.capture_id, job.id)
        except JobDispatchError as error:
            raise CaptureError(
                "processing_dispatch_unavailable",
                "The upload is safe, but processing could not start; retry this request",
                details={
                    "capture_id": str(job.capture_id),
                    "job_id": str(job.id),
                    "retryable": True,
                },
            ) from error
        return job
