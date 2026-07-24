from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    JobState,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.infrastructure.models import (
    CaptureRecord,
    ProcessingJobRecord,
)
from stylecapture_backend.features.capture.ports import CaptureSubmission


class SqlAlchemyCaptureRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def find_by_idempotency(
        self,
        user_id: UUID,
        idempotency_key: str,
    ) -> CaptureSubmission | None:
        async with self._sessions() as session:
            statement = (
                select(CaptureRecord, ProcessingJobRecord)
                .join(ProcessingJobRecord, ProcessingJobRecord.capture_id == CaptureRecord.id)
                .where(
                    CaptureRecord.user_id == user_id,
                    CaptureRecord.idempotency_key == idempotency_key,
                )
            )
            row = (await session.execute(statement)).one_or_none()
            if row is None:
                return None
            return CaptureSubmission(
                capture=_capture_from_record(row[0]),
                job=_job_from_record(row[1]),
            )

    async def get_capture(self, capture_id: UUID) -> Capture | None:
        async with self._sessions() as session:
            record = await session.get(CaptureRecord, capture_id)
            return _capture_from_record(record) if record is not None else None

    async def save_submission(
        self,
        capture: Capture,
        job: ProcessingJob,
        idempotency_key: str,
    ) -> CaptureSubmission:
        async with self._sessions() as session:
            session.add(_capture_record(capture, idempotency_key))
            session.add(_job_record(job))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                existing = await self.find_by_idempotency(capture.user_id, idempotency_key)
                if existing is None:
                    raise
                return existing
        return CaptureSubmission(capture=capture, job=job)

    async def get_for_user(self, job_id: UUID, user_id: UUID) -> ProcessingJob | None:
        async with self._sessions() as session:
            statement = (
                select(ProcessingJobRecord)
                .join(CaptureRecord, CaptureRecord.id == ProcessingJobRecord.capture_id)
                .where(ProcessingJobRecord.id == job_id, CaptureRecord.user_id == user_id)
            )
            record = (await session.execute(statement)).scalar_one_or_none()
            return _job_from_record(record) if record is not None else None

    async def get_job(self, job_id: UUID) -> ProcessingJob | None:
        async with self._sessions() as session:
            record = await session.get(ProcessingJobRecord, job_id)
            return _job_from_record(record) if record is not None else None

    async def update(self, job: ProcessingJob) -> ProcessingJob:
        async with self._sessions() as session:
            record = await session.get(ProcessingJobRecord, job.id, with_for_update=True)
            if record is None:
                raise KeyError(job.id)
            record.state = job.state.value
            record.attempt = job.attempt
            record.error_code = job.error_code
            record.error_message = job.error_message
            record.updated_at = job.updated_at
            await session.commit()
        return job


def _capture_record(capture: Capture, idempotency_key: str) -> CaptureRecord:
    return CaptureRecord(
        id=capture.id,
        user_id=capture.user_id,
        source_kind=capture.source.kind.value,
        object_key=capture.source.object_key,
        sha256=capture.source.sha256,
        ownership=capture.ownership.value,
        idempotency_key=idempotency_key,
        created_at=capture.created_at,
    )


def _job_record(job: ProcessingJob) -> ProcessingJobRecord:
    return ProcessingJobRecord(
        id=job.id,
        capture_id=job.capture_id,
        state=job.state.value,
        attempt=job.attempt,
        error_code=job.error_code,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _capture_from_record(record: CaptureRecord) -> Capture:
    return Capture(
        id=record.id,
        user_id=record.user_id,
        source=CaptureSource(
            kind=CaptureSourceKind(record.source_kind),
            object_key=record.object_key,
            sha256=record.sha256,
        ),
        ownership=OwnershipState(record.ownership),
        created_at=record.created_at,
    )


def _job_from_record(record: ProcessingJobRecord) -> ProcessingJob:
    return ProcessingJob(
        id=record.id,
        capture_id=record.capture_id,
        state=JobState(record.state),
        attempt=record.attempt,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error_code=record.error_code,
        error_message=record.error_message,
    )
