from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stylecapture_backend.features.look.infrastructure.models import LookRecord
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderArtifactStatus,
    RenderInputSignature,
    RenderOutput,
    RenderPrivacy,
    RenderProviderTrace,
)
from stylecapture_backend.features.render.infrastructure.models import RenderArtifactRecord
from stylecapture_backend.features.render.ports import (
    RenderIdempotencyConflict,
    RenderPersistenceUnavailable,
)


class SqlAlchemyRenderArtifactRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def ensure_requested(self, artifact: RenderArtifact) -> RenderArtifact:
        try:
            async with self._sessions() as session:
                await _lock_owned_look(session, artifact.look_id, artifact.user_id)
                existing_request = (
                    await session.execute(
                        select(RenderArtifactRecord).where(
                            RenderArtifactRecord.user_id == artifact.user_id,
                            RenderArtifactRecord.request_key == artifact.request_key,
                        )
                    )
                ).scalar_one_or_none()
                if existing_request is not None:
                    _raise_on_idempotency_conflict(existing_request, artifact)
                    return _artifact_from_record(existing_request)
                equivalent = (
                    (
                        await session.execute(
                            select(RenderArtifactRecord)
                            .where(
                                RenderArtifactRecord.user_id == artifact.user_id,
                                RenderArtifactRecord.look_id == artifact.look_id,
                                RenderArtifactRecord.kind == artifact.kind.value,
                                RenderArtifactRecord.input_version
                                == artifact.input_signature.version,
                                RenderArtifactRecord.input_hash == artifact.input_signature.hash,
                                RenderArtifactRecord.privacy == artifact.privacy.value,
                                RenderArtifactRecord.source_artifact_id
                                == artifact.source_artifact_id,
                                RenderArtifactRecord.subject_object_key
                                == artifact.subject_object_key,
                                RenderArtifactRecord.status.in_(
                                    (
                                        RenderArtifactStatus.QUEUED.value,
                                        RenderArtifactStatus.RUNNING.value,
                                        RenderArtifactStatus.SUCCEEDED.value,
                                    )
                                ),
                            )
                            .order_by(RenderArtifactRecord.created_at)
                        )
                    )
                    .scalars()
                    .first()
                )
                if equivalent is not None:
                    return _artifact_from_record(equivalent)
                await session.execute(
                    insert(RenderArtifactRecord)
                    .values(**_artifact_values(artifact))
                    .on_conflict_do_nothing(index_elements=["user_id", "request_key"])
                )
                stored = (
                    await session.execute(
                        select(RenderArtifactRecord).where(
                            RenderArtifactRecord.user_id == artifact.user_id,
                            RenderArtifactRecord.request_key == artifact.request_key,
                        )
                    )
                ).scalar_one()
                _raise_on_idempotency_conflict(stored, artifact)
                await session.commit()
                return _artifact_from_record(stored)
        except OperationalError as error:
            raise RenderPersistenceUnavailable(
                "Render artifact persistence is temporarily unavailable"
            ) from error

    async def save(self, artifact: RenderArtifact) -> RenderArtifact:
        try:
            async with self._sessions() as session:
                await _raise_if_look_owner_mismatch(session, artifact.look_id, artifact.user_id)
                current_record = (
                    await session.execute(
                        select(RenderArtifactRecord)
                        .where(
                            RenderArtifactRecord.id == artifact.id,
                            RenderArtifactRecord.user_id == artifact.user_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if current_record is not None:
                    current_status = RenderArtifactStatus(current_record.status)
                    terminal = {
                        RenderArtifactStatus.SUCCEEDED,
                        RenderArtifactStatus.FAILED,
                        RenderArtifactStatus.DEGRADED,
                    }
                    if current_status in terminal and artifact.status is not current_status:
                        return _artifact_from_record(current_record)
                values = _artifact_values(artifact)
                if current_record is not None:
                    current_record.status = artifact.status.value
                    current_record.object_key = cast(str | None, values["object_key"])
                    current_record.content_hash = cast(str | None, values["content_hash"])
                    current_record.content_type = cast(str | None, values["content_type"])
                    current_record.sprite_object_key = cast(str | None, values["sprite_object_key"])
                    current_record.sprite_content_hash = cast(
                        str | None, values["sprite_content_hash"]
                    )
                    current_record.sprite_content_type = cast(
                        str | None, values["sprite_content_type"]
                    )
                    current_record.share_eligible = cast(bool, values["share_eligible"])
                    current_record.source_artifact_id = artifact.source_artifact_id
                    current_record.fallback_artifact_id = artifact.fallback_artifact_id
                    current_record.failure_code = artifact.failure_code
                    current_record.failure_message = artifact.failure_message
                    current_record.provider_trace = cast(
                        dict[str, object] | None,
                        values["provider_trace"],
                    )
                    current_record.subject_object_key = artifact.subject_object_key
                    current_record.updated_at = artifact.updated_at
                    await session.commit()
                    return _artifact_from_record(current_record)
                stored = (
                    await session.execute(
                        insert(RenderArtifactRecord)
                        .values(**values)
                        .on_conflict_do_update(
                            index_elements=["id"],
                            set_={
                                "status": artifact.status.value,
                                "object_key": values["object_key"],
                                "content_hash": values["content_hash"],
                                "content_type": values["content_type"],
                                "sprite_object_key": values["sprite_object_key"],
                                "sprite_content_hash": values["sprite_content_hash"],
                                "sprite_content_type": values["sprite_content_type"],
                                "share_eligible": values["share_eligible"],
                                "source_artifact_id": artifact.source_artifact_id,
                                "fallback_artifact_id": artifact.fallback_artifact_id,
                                "failure_code": artifact.failure_code,
                                "failure_message": artifact.failure_message,
                                "provider_trace": values["provider_trace"],
                                "subject_object_key": artifact.subject_object_key,
                                "updated_at": artifact.updated_at,
                            },
                        )
                        .returning(RenderArtifactRecord)
                    )
                ).scalar_one()
                await session.commit()
                return _artifact_from_record(stored)
        except OperationalError as error:
            raise RenderPersistenceUnavailable(
                "Render artifact persistence is temporarily unavailable"
            ) from error

    async def claim_queued_for_recovery(
        self,
        *,
        user_id: UUID,
        artifact_id: UUID,
        stale_before: datetime,
    ) -> RenderArtifact | None:
        try:
            async with self._sessions() as session:
                record = (
                    await session.execute(
                        update(RenderArtifactRecord)
                        .where(
                            RenderArtifactRecord.id == artifact_id,
                            RenderArtifactRecord.user_id == user_id,
                            RenderArtifactRecord.status == RenderArtifactStatus.QUEUED.value,
                            RenderArtifactRecord.updated_at <= stale_before,
                        )
                        .values(updated_at=datetime.now(UTC))
                        .returning(RenderArtifactRecord)
                    )
                ).scalar_one_or_none()
                await session.commit()
                return _artifact_from_record(record) if record is not None else None
        except OperationalError as error:
            raise RenderPersistenceUnavailable(
                "Render artifact persistence is temporarily unavailable"
            ) from error

    async def find_cache_hit(
        self,
        *,
        look_id: UUID,
        kind: RenderArtifactKind,
        input_signature: RenderInputSignature,
    ) -> RenderArtifact | None:
        async with self._sessions() as session:
            record = (
                await session.execute(
                    select(RenderArtifactRecord)
                    .where(
                        RenderArtifactRecord.look_id == look_id,
                        RenderArtifactRecord.kind == kind.value,
                        RenderArtifactRecord.input_version == input_signature.version,
                        RenderArtifactRecord.input_hash == input_signature.hash,
                        RenderArtifactRecord.status == RenderArtifactStatus.SUCCEEDED.value,
                        RenderArtifactRecord.object_key.is_not(None),
                    )
                    .order_by(RenderArtifactRecord.updated_at.desc())
                )
            ).scalar_one_or_none()
            return _artifact_from_record(record) if record is not None else None

    async def list_for_look(self, *, user_id: UUID, look_id: UUID) -> list[RenderArtifact]:
        async with self._sessions() as session:
            records = (
                await session.scalars(
                    select(RenderArtifactRecord)
                    .where(
                        RenderArtifactRecord.user_id == user_id,
                        RenderArtifactRecord.look_id == look_id,
                    )
                    .order_by(RenderArtifactRecord.created_at)
                )
            ).all()
            return [_artifact_from_record(record) for record in records]

    async def get_for_user(self, *, user_id: UUID, artifact_id: UUID) -> RenderArtifact | None:
        async with self._sessions() as session:
            record = (
                await session.execute(
                    select(RenderArtifactRecord).where(
                        RenderArtifactRecord.id == artifact_id,
                        RenderArtifactRecord.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
            return _artifact_from_record(record) if record is not None else None


async def _raise_if_look_owner_mismatch(
    session: AsyncSession,
    look_id: UUID,
    user_id: UUID,
) -> None:
    owner_id = (
        await session.execute(select(LookRecord.user_id).where(LookRecord.id == look_id))
    ).scalar_one_or_none()
    if owner_id is not None and owner_id != user_id:
        raise ValueError("render artifact Look belongs to another user")


async def _lock_owned_look(
    session: AsyncSession,
    look_id: UUID,
    user_id: UUID,
) -> None:
    owner_id = (
        await session.execute(
            select(LookRecord.user_id).where(LookRecord.id == look_id).with_for_update()
        )
    ).scalar_one_or_none()
    if owner_id is not None and owner_id != user_id:
        raise ValueError("render artifact Look belongs to another user")


def _artifact_values(artifact: RenderArtifact) -> dict[str, object]:
    output = artifact.output
    sprite = artifact.sprite_output
    return {
        "id": artifact.id,
        "user_id": artifact.user_id,
        "look_id": artifact.look_id,
        "kind": artifact.kind.value,
        "status": artifact.status.value,
        "input_version": artifact.input_signature.version,
        "input_hash": artifact.input_signature.hash,
        "request_key": artifact.request_key,
        "privacy": artifact.privacy.value,
        "object_key": output.object_key if output is not None else None,
        "content_hash": output.content_hash if output is not None else None,
        "content_type": output.content_type if output is not None else None,
        "sprite_object_key": sprite.object_key if sprite is not None else None,
        "sprite_content_hash": sprite.content_hash if sprite is not None else None,
        "sprite_content_type": sprite.content_type if sprite is not None else None,
        "share_eligible": artifact.share_eligible,
        "source_artifact_id": artifact.source_artifact_id,
        "fallback_artifact_id": artifact.fallback_artifact_id,
        "failure_code": artifact.failure_code,
        "failure_message": artifact.failure_message,
        "provider_trace": _trace_to_json(artifact.provider_trace),
        "subject_object_key": artifact.subject_object_key,
        "created_at": artifact.created_at,
        "updated_at": artifact.updated_at,
    }


def _artifact_from_record(record: RenderArtifactRecord) -> RenderArtifact:
    output = (
        RenderOutput(
            object_key=cast(str, record.object_key),
            content_hash=cast(str, record.content_hash),
            content_type=cast(str, record.content_type),
        )
        if record.object_key is not None
        else None
    )
    sprite_output = (
        RenderOutput(
            object_key=cast(str, record.sprite_object_key),
            content_hash=cast(str, record.sprite_content_hash),
            content_type=cast(str, record.sprite_content_type),
        )
        if record.sprite_object_key is not None
        else None
    )
    return RenderArtifact(
        id=record.id,
        user_id=record.user_id,
        look_id=record.look_id,
        kind=RenderArtifactKind(record.kind),
        status=RenderArtifactStatus(record.status),
        input_signature=RenderInputSignature(
            version=record.input_version,
            hash=record.input_hash,
        ),
        request_key=record.request_key,
        privacy=RenderPrivacy(record.privacy),
        output=output,
        source_artifact_id=record.source_artifact_id,
        fallback_artifact_id=record.fallback_artifact_id,
        failure_code=record.failure_code,
        failure_message=record.failure_message,
        provider_trace=_trace_from_json(record.provider_trace),
        created_at=record.created_at,
        updated_at=record.updated_at,
        subject_object_key=record.subject_object_key,
        sprite_output=sprite_output,
    )


def _trace_to_json(trace: RenderProviderTrace | None) -> dict[str, object] | None:
    if trace is None:
        return None
    return {
        "provider": trace.provider,
        "model": trace.model,
        "parameters": dict(trace.parameters),
    }


def _trace_from_json(payload: Mapping[str, object] | None) -> RenderProviderTrace | None:
    if payload is None:
        return None
    return RenderProviderTrace(
        provider=str(payload["provider"]),
        model=str(payload["model"]),
        parameters=cast(Mapping[str, object], payload["parameters"]),
    )


def _raise_on_idempotency_conflict(
    stored: RenderArtifactRecord,
    expected: RenderArtifact,
) -> None:
    if (
        stored.look_id != expected.look_id
        or stored.kind != expected.kind.value
        or stored.input_version != expected.input_signature.version
        or stored.input_hash != expected.input_signature.hash
        or stored.privacy != expected.privacy.value
        or stored.source_artifact_id != expected.source_artifact_id
        or stored.subject_object_key != expected.subject_object_key
    ):
        raise RenderIdempotencyConflict(
            "render request key already represents another render request"
        )
