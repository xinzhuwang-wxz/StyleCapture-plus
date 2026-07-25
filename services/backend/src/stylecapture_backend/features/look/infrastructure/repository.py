from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stylecapture_backend.features.capture.domain import NormalizedPoint
from stylecapture_backend.features.look.domain import (
    Look,
    LookAnalysis,
    LookAnalysisField,
    LookAnalysisMetadata,
    LookComponent,
    LookComponentStatus,
    LookDetail,
    LookSource,
    LookStatus,
    PreferenceSignal,
    PreferenceSignalKind,
)
from stylecapture_backend.features.look.infrastructure.models import (
    LookComponentRecord,
    LookRecord,
    PreferenceSignalRecord,
)
from stylecapture_backend.features.look.ports import (
    LookItemOwnershipMismatch,
    LookPersistenceUnavailable,
    PreferenceIdempotencyConflict,
)
from stylecapture_backend.features.wardrobe.infrastructure.models import ItemRecord


class SqlAlchemyLookRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def ensure_placeholder(
        self,
        look: Look,
        signal: PreferenceSignal,
    ) -> Look:
        try:
            async with self._sessions() as session:
                await session.execute(
                    insert(LookRecord)
                    .values(**_look_values(look))
                    .on_conflict_do_nothing(index_elements=["capture_id", "source_selection_key"])
                )
                stored_record = (
                    await session.execute(
                        select(LookRecord).where(
                            LookRecord.capture_id == look.capture_id,
                            LookRecord.source_selection_key == look.source_selection_key,
                        )
                    )
                ).scalar_one()
                stored_signal = PreferenceSignal(
                    id=signal.id,
                    user_id=signal.user_id,
                    look_id=stored_record.id,
                    kind=signal.kind,
                    payload=signal.payload,
                    idempotency_key=signal.idempotency_key,
                    created_at=signal.created_at,
                )
                await session.execute(
                    insert(PreferenceSignalRecord)
                    .values(**_preference_values(stored_signal))
                    .on_conflict_do_nothing(index_elements=["user_id", "idempotency_key"])
                )
                stored_preference = (
                    await session.execute(
                        select(PreferenceSignalRecord).where(
                            PreferenceSignalRecord.user_id == stored_signal.user_id,
                            PreferenceSignalRecord.idempotency_key == stored_signal.idempotency_key,
                        )
                    )
                ).scalar_one()
                _raise_on_preference_idempotency_conflict(
                    stored_preference,
                    stored_signal,
                )
                await session.commit()
                return _look_from_record(stored_record)
        except OperationalError as error:
            raise LookPersistenceUnavailable(
                "Look persistence is temporarily unavailable"
            ) from error

    async def list_for_user(self, user_id: UUID) -> list[Look]:
        async with self._sessions() as session:
            records = (
                await session.scalars(
                    select(LookRecord)
                    .where(LookRecord.user_id == user_id)
                    .order_by(LookRecord.created_at.desc())
                    .limit(100)
                )
            ).all()
            return [_look_from_record(record) for record in records]

    async def get_by_capture(
        self,
        capture_id: UUID,
        source_selection_key: str,
    ) -> Look | None:
        async with self._sessions() as session:
            record = (
                await session.execute(
                    select(LookRecord).where(
                        LookRecord.capture_id == capture_id,
                        LookRecord.source_selection_key == source_selection_key,
                    )
                )
            ).scalar_one_or_none()
            return _look_from_record(record) if record is not None else None

    async def get_detail_for_user(
        self,
        look_id: UUID,
        user_id: UUID,
    ) -> LookDetail | None:
        async with self._sessions() as session:
            look_record = (
                await session.execute(
                    select(LookRecord).where(
                        LookRecord.id == look_id,
                        LookRecord.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
            if look_record is None:
                return None
            component_records = (
                await session.scalars(
                    select(LookComponentRecord)
                    .where(LookComponentRecord.look_id == look_id)
                    .order_by(
                        LookComponentRecord.display_order,
                        LookComponentRecord.created_at,
                    )
                )
            ).all()
            preference_records = (
                await session.scalars(
                    select(PreferenceSignalRecord)
                    .where(
                        PreferenceSignalRecord.look_id == look_id,
                        PreferenceSignalRecord.user_id == user_id,
                    )
                    .order_by(PreferenceSignalRecord.created_at)
                )
            ).all()
            return LookDetail(
                look=_look_from_record(look_record),
                components=tuple(_component_from_record(record) for record in component_records),
                preference_signals=tuple(
                    _preference_from_record(record) for record in preference_records
                ),
            )

    async def append_preference(
        self,
        signal: PreferenceSignal,
    ) -> PreferenceSignal:
        async with self._sessions() as session:
            await session.execute(
                insert(PreferenceSignalRecord)
                .values(**_preference_values(signal))
                .on_conflict_do_nothing(index_elements=["user_id", "idempotency_key"])
            )
            stored = (
                await session.execute(
                    select(PreferenceSignalRecord).where(
                        PreferenceSignalRecord.user_id == signal.user_id,
                        PreferenceSignalRecord.idempotency_key == signal.idempotency_key,
                    )
                )
            ).scalar_one()
            _raise_on_preference_idempotency_conflict(stored, signal)
            await session.commit()
            return _preference_from_record(stored)

    async def save(self, look: Look) -> Look:
        async with self._sessions() as session:
            values = _look_values(look)
            stored = (
                await session.execute(
                    insert(LookRecord)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=["capture_id", "source_selection_key"],
                        set_={
                            "status": look.status.value,
                            "analysis": values["analysis"],
                            "display_object_key": look.display_object_key,
                            "updated_at": look.updated_at,
                        },
                    )
                    .returning(LookRecord)
                )
            ).scalar_one()
            await session.commit()
            return _look_from_record(stored)

    async def save_component(self, component: LookComponent) -> LookComponent:
        async with self._sessions() as session:
            if component.item_id is not None:
                owners = (
                    await session.execute(
                        select(LookRecord.user_id, ItemRecord.user_id)
                        .join(ItemRecord, ItemRecord.id == component.item_id)
                        .where(LookRecord.id == component.look_id)
                    )
                ).one_or_none()
                if owners is not None and owners[0] != owners[1]:
                    raise LookItemOwnershipMismatch("component Item belongs to another user")
            values = _component_values(component)
            await session.execute(
                insert(LookComponentRecord)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=["look_id", "component_key"],
                    set_={
                        "status": component.status.value,
                        "item_id": component.item_id,
                        "evidence_region": values["evidence_region"],
                        "role": component.role,
                        "layer": component.layer,
                        "display_order": component.display_order,
                        "confidence": component.confidence,
                        "grounding_metadata": values["grounding_metadata"],
                        "updated_at": component.updated_at,
                    },
                )
            )
            stored = (
                await session.execute(
                    select(LookComponentRecord).where(
                        LookComponentRecord.look_id == component.look_id,
                        LookComponentRecord.component_key == component.component_key,
                    )
                )
            ).scalar_one()
            await session.commit()
            return _component_from_record(stored)


def _look_values(look: Look) -> dict[str, object]:
    return {
        "id": look.id,
        "user_id": look.user_id,
        "capture_id": look.capture_id,
        "source_selection_key": look.source_selection_key,
        "source": look.source.value,
        "status": look.status.value,
        "analysis": _analysis_to_json(look.analysis),
        "display_object_key": look.display_object_key,
        "created_at": look.created_at,
        "updated_at": look.updated_at,
    }


def _look_from_record(record: LookRecord) -> Look:
    return Look(
        id=record.id,
        user_id=record.user_id,
        capture_id=record.capture_id,
        source_selection_key=record.source_selection_key,
        source=LookSource(record.source),
        status=LookStatus(record.status),
        analysis=_analysis_from_json(record.analysis),
        display_object_key=record.display_object_key,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _component_values(component: LookComponent) -> dict[str, object]:
    return {
        "id": component.id,
        "look_id": component.look_id,
        "component_key": component.component_key,
        "status": component.status.value,
        "item_id": component.item_id,
        "evidence_region": [{"x": point.x, "y": point.y} for point in component.evidence_region],
        "role": component.role,
        "layer": component.layer,
        "display_order": component.display_order,
        "confidence": component.confidence,
        "grounding_metadata": dict(component.grounding_metadata),
        "created_at": component.created_at,
        "updated_at": component.updated_at,
    }


def _component_from_record(record: LookComponentRecord) -> LookComponent:
    return LookComponent(
        id=record.id,
        look_id=record.look_id,
        component_key=record.component_key,
        status=LookComponentStatus(record.status),
        item_id=record.item_id,
        evidence_region=tuple(
            NormalizedPoint(float(point["x"]), float(point["y"]))
            for point in record.evidence_region
        ),
        role=record.role,
        layer=record.layer,
        display_order=record.display_order,
        confidence=record.confidence,
        grounding_metadata=record.grounding_metadata,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _preference_values(signal: PreferenceSignal) -> dict[str, object]:
    return {
        "id": signal.id,
        "user_id": signal.user_id,
        "look_id": signal.look_id,
        "kind": signal.kind.value,
        "payload": dict(signal.payload),
        "idempotency_key": signal.idempotency_key,
        "created_at": signal.created_at,
    }


def _preference_from_record(record: PreferenceSignalRecord) -> PreferenceSignal:
    return PreferenceSignal(
        id=record.id,
        user_id=record.user_id,
        look_id=record.look_id,
        kind=PreferenceSignalKind(record.kind),
        payload=record.payload,
        idempotency_key=record.idempotency_key,
        created_at=record.created_at,
    )


def _raise_on_preference_idempotency_conflict(
    stored: PreferenceSignalRecord,
    expected: PreferenceSignal,
) -> None:
    if (
        stored.look_id != expected.look_id
        or stored.kind != expected.kind.value
        or stored.payload != dict(expected.payload)
    ):
        raise PreferenceIdempotencyConflict(
            "preference idempotency conflict: key already represents another event"
        )


def _analysis_to_json(analysis: LookAnalysis | None) -> dict[str, object] | None:
    if analysis is None:
        return None
    fields: dict[str, object] = {
        name: {
            "value": field.value,
            "confidence": field.confidence,
        }
        for name, field in (
            ("color", analysis.color),
            ("silhouette", analysis.silhouette),
            ("material", analysis.material),
            ("layering", analysis.layering),
            ("focal_point", analysis.focal_point),
            ("scene", analysis.scene),
            ("style", analysis.style),
        )
    }
    fields["metadata"] = {
        "capability_alias": analysis.metadata.capability_alias,
        "provider_model": analysis.metadata.provider_model,
        "prompt_version": analysis.metadata.prompt_version,
        "schema_version": analysis.metadata.schema_version,
        "taxonomy_version": analysis.metadata.taxonomy_version,
        "latency_ms": analysis.metadata.latency_ms,
    }
    return fields


def _analysis_from_json(payload: Mapping[str, object] | None) -> LookAnalysis | None:
    if payload is None:
        return None

    def field(name: str) -> LookAnalysisField:
        raw = cast(Mapping[str, object], payload[name])
        return LookAnalysisField(
            value=str(raw["value"]),
            confidence=float(cast(float, raw["confidence"])),
        )

    raw_metadata = cast(Mapping[str, object], payload["metadata"])
    return LookAnalysis(
        color=field("color"),
        silhouette=field("silhouette"),
        material=field("material"),
        layering=field("layering"),
        focal_point=field("focal_point"),
        scene=field("scene"),
        style=field("style"),
        metadata=LookAnalysisMetadata(
            capability_alias=str(raw_metadata["capability_alias"]),
            provider_model=str(raw_metadata["provider_model"]),
            prompt_version=str(raw_metadata["prompt_version"]),
            schema_version=str(raw_metadata["schema_version"]),
            taxonomy_version=str(raw_metadata["taxonomy_version"]),
            latency_ms=int(cast(int, raw_metadata["latency_ms"])),
        ),
    )
