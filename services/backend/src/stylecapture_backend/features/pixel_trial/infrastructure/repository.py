from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from stylecapture_backend.features.pixel_trial.domain import PixelTrial, PixelTrialStatus
from stylecapture_backend.features.pixel_trial.infrastructure.models import PixelTrialRecord
from stylecapture_backend.features.pixel_trial.ports import (
    PixelTrialIdempotencyConflict,
    PixelTrialPersistenceUnavailable,
)
from stylecapture_backend.features.render.domain import (
    RenderOutput,
    RenderProviderTrace,
)


class SqlAlchemyPixelTrialRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def ensure_requested(self, trial: PixelTrial) -> PixelTrial:
        try:
            async with self._sessions() as session:
                existing = (
                    await session.execute(
                        select(PixelTrialRecord).where(
                            PixelTrialRecord.user_id == trial.user_id,
                            PixelTrialRecord.request_key == trial.request_key,
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    _raise_on_idempotency_conflict(existing, trial)
                    return _trial_from_record(existing)
                await session.execute(
                    insert(PixelTrialRecord)
                    .values(**_trial_values(trial))
                    .on_conflict_do_nothing(index_elements=["user_id", "request_key"])
                )
                stored = (
                    await session.execute(
                        select(PixelTrialRecord).where(
                            PixelTrialRecord.user_id == trial.user_id,
                            PixelTrialRecord.request_key == trial.request_key,
                        )
                    )
                ).scalar_one()
                _raise_on_idempotency_conflict(stored, trial)
                await session.commit()
                return _trial_from_record(stored)
        except OperationalError as error:
            raise PixelTrialPersistenceUnavailable(
                "Pixel trial persistence is temporarily unavailable"
            ) from error

    async def save(self, trial: PixelTrial) -> PixelTrial:
        try:
            async with self._sessions() as session:
                record = (
                    await session.execute(
                        select(PixelTrialRecord)
                        .where(
                            PixelTrialRecord.id == trial.id,
                            PixelTrialRecord.user_id == trial.user_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                values = _trial_values(trial)
                if record is not None:
                    if (
                        PixelTrialStatus(record.status)
                        in {
                            PixelTrialStatus.SUCCEEDED,
                            PixelTrialStatus.FAILED,
                        }
                        and PixelTrialStatus(record.status) is not trial.status
                    ):
                        return _trial_from_record(record)
                    record.status = trial.status.value
                    record.subject_object_key = trial.subject_object_key
                    record.subject_attached = trial.subject_object_key is not None
                    record.object_key = cast(str | None, values["object_key"])
                    record.content_hash = cast(str | None, values["content_hash"])
                    record.content_type = cast(str | None, values["content_type"])
                    record.failure_code = trial.failure_code
                    record.failure_message = trial.failure_message
                    record.provider_trace = cast(dict[str, object] | None, values["provider_trace"])
                    record.updated_at = trial.updated_at
                    await session.commit()
                    return _trial_from_record(record)
                stored = (
                    await session.execute(
                        insert(PixelTrialRecord)
                        .values(**values)
                        .on_conflict_do_update(
                            index_elements=["id"],
                            set_={
                                "status": trial.status.value,
                                "subject_object_key": trial.subject_object_key,
                                "subject_attached": trial.subject_object_key is not None,
                                "object_key": values["object_key"],
                                "content_hash": values["content_hash"],
                                "content_type": values["content_type"],
                                "failure_code": trial.failure_code,
                                "failure_message": trial.failure_message,
                                "provider_trace": values["provider_trace"],
                                "updated_at": trial.updated_at,
                            },
                        )
                        .returning(PixelTrialRecord)
                    )
                ).scalar_one()
                await session.commit()
                return _trial_from_record(stored)
        except OperationalError as error:
            raise PixelTrialPersistenceUnavailable(
                "Pixel trial persistence is temporarily unavailable"
            ) from error

    async def get_for_user(self, *, user_id: UUID, trial_id: UUID) -> PixelTrial | None:
        async with self._sessions() as session:
            record = (
                await session.execute(
                    select(PixelTrialRecord).where(
                        PixelTrialRecord.id == trial_id,
                        PixelTrialRecord.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
            return _trial_from_record(record) if record is not None else None

    async def delete_for_user(self, *, user_id: UUID, trial_id: UUID) -> PixelTrial | None:
        async with self._sessions() as session:
            record = (
                await session.execute(
                    delete(PixelTrialRecord)
                    .where(PixelTrialRecord.id == trial_id, PixelTrialRecord.user_id == user_id)
                    .returning(PixelTrialRecord)
                )
            ).scalar_one_or_none()
            await session.commit()
            return _trial_from_record(record) if record is not None else None


def _trial_values(trial: PixelTrial) -> dict[str, object | None]:
    return {
        "id": trial.id,
        "user_id": trial.user_id,
        "status": trial.status.value,
        "subject_object_key": trial.subject_object_key,
        "request_key": trial.request_key,
        "object_key": trial.output.object_key if trial.output is not None else None,
        "content_hash": trial.output.content_hash if trial.output is not None else None,
        "content_type": trial.output.content_type if trial.output is not None else None,
        "subject_attached": trial.subject_object_key is not None,
        "failure_code": trial.failure_code,
        "failure_message": trial.failure_message,
        "provider_trace": (
            {
                "provider": trial.provider_trace.provider,
                "model": trial.provider_trace.model,
                "parameters": dict(trial.provider_trace.parameters),
            }
            if trial.provider_trace is not None
            else None
        ),
        "created_at": trial.created_at,
        "updated_at": trial.updated_at,
    }


def _trial_from_record(record: PixelTrialRecord) -> PixelTrial:
    return PixelTrial(
        id=record.id,
        user_id=record.user_id,
        status=PixelTrialStatus(record.status),
        subject_object_key=record.subject_object_key,
        request_key=record.request_key,
        output=(
            RenderOutput(
                object_key=record.object_key,
                content_hash=record.content_hash,
                content_type=record.content_type,
            )
            if record.object_key is not None
            and record.content_hash is not None
            and record.content_type is not None
            else None
        ),
        failure_code=record.failure_code,
        failure_message=record.failure_message,
        provider_trace=_trace_from_mapping(record.provider_trace),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _trace_from_mapping(payload: Mapping[str, object] | None) -> RenderProviderTrace | None:
    if payload is None:
        return None
    parameters = payload.get("parameters")
    return RenderProviderTrace(
        provider=str(payload["provider"]),
        model=str(payload["model"]),
        parameters=dict(parameters) if isinstance(parameters, Mapping) else {},
    )


def _raise_on_idempotency_conflict(record: PixelTrialRecord, trial: PixelTrial) -> None:
    if record.subject_object_key != trial.subject_object_key:
        raise PixelTrialIdempotencyConflict(
            "Pixel trial idempotency key was reused with a different subject"
        )
