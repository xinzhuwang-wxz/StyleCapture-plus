from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationAsset,
    ItemPresentationKind,
    ItemPresentationStatus,
)
from stylecapture_backend.features.item_presentation.infrastructure.models import (
    ItemPresentationAssetRecord,
)
from stylecapture_backend.features.item_presentation.ports import (
    ItemPresentationIdempotencyConflict,
    ItemPresentationPersistenceUnavailable,
)
from stylecapture_backend.features.render.domain import (
    RenderInputSignature,
    RenderOutput,
    RenderProviderTrace,
)


class SqlAlchemyItemPresentationRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def ensure_requested(
        self,
        asset: ItemPresentationAsset,
    ) -> ItemPresentationAsset:
        try:
            async with self._sessions() as session:
                existing_request = (
                    await session.execute(
                        select(ItemPresentationAssetRecord).where(
                            ItemPresentationAssetRecord.user_id == asset.user_id,
                            ItemPresentationAssetRecord.request_key == asset.request_key,
                        )
                    )
                ).scalar_one_or_none()
                if existing_request is not None:
                    _raise_on_idempotency_conflict(existing_request, asset)
                    return _asset_from_record(existing_request)
                equivalent = await _find_equivalent(session, asset)
                if equivalent is not None:
                    return _asset_from_record(equivalent)
                await session.execute(
                    insert(ItemPresentationAssetRecord)
                    .values(**_asset_values(asset))
                    .on_conflict_do_nothing()
                )
                stored_request = (
                    await session.execute(
                        select(ItemPresentationAssetRecord).where(
                            ItemPresentationAssetRecord.user_id == asset.user_id,
                            ItemPresentationAssetRecord.request_key == asset.request_key,
                        )
                    )
                ).scalar_one_or_none()
                stored: ItemPresentationAssetRecord | None
                if stored_request is not None:
                    _raise_on_idempotency_conflict(stored_request, asset)
                    stored = stored_request
                else:
                    stored = await _find_equivalent(session, asset)
                    if stored is None:
                        raise ItemPresentationPersistenceUnavailable(
                            "Equivalent item presentation was not visible after insert"
                        )
                await session.commit()
                return _asset_from_record(stored)
        except OperationalError as error:
            raise ItemPresentationPersistenceUnavailable(
                "Item presentation persistence is temporarily unavailable"
            ) from error

    async def save(self, asset: ItemPresentationAsset) -> ItemPresentationAsset:
        try:
            async with self._sessions() as session:
                record = (
                    await session.execute(
                        select(ItemPresentationAssetRecord)
                        .where(
                            ItemPresentationAssetRecord.id == asset.id,
                            ItemPresentationAssetRecord.user_id == asset.user_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                values = _asset_values(asset)
                if record is not None:
                    current_status = ItemPresentationStatus(record.status)
                    if (
                        current_status is ItemPresentationStatus.SUCCEEDED
                        and asset.status is not ItemPresentationStatus.QUEUED
                        and current_status is not asset.status
                    ):
                        return _asset_from_record(record)
                    if (
                        current_status is ItemPresentationStatus.FAILED
                        and asset.status is not ItemPresentationStatus.QUEUED
                        and current_status is not asset.status
                    ):
                        return _asset_from_record(record)
                    record.status = asset.status.value
                    record.object_key = cast(str | None, values["object_key"])
                    record.content_hash = cast(str | None, values["content_hash"])
                    record.content_type = cast(str | None, values["content_type"])
                    record.failure_code = asset.failure_code
                    record.failure_message = asset.failure_message
                    record.provider_trace = cast(dict[str, object] | None, values["provider_trace"])
                    record.updated_at = asset.updated_at
                    await session.commit()
                    return _asset_from_record(record)
                stored = (
                    await session.execute(
                        insert(ItemPresentationAssetRecord)
                        .values(**values)
                        .on_conflict_do_update(
                            index_elements=["id"],
                            set_={
                                "status": asset.status.value,
                                "object_key": values["object_key"],
                                "content_hash": values["content_hash"],
                                "content_type": values["content_type"],
                                "failure_code": asset.failure_code,
                                "failure_message": asset.failure_message,
                                "provider_trace": values["provider_trace"],
                                "updated_at": asset.updated_at,
                            },
                        )
                        .returning(ItemPresentationAssetRecord)
                    )
                ).scalar_one()
                await session.commit()
                return _asset_from_record(stored)
        except OperationalError as error:
            raise ItemPresentationPersistenceUnavailable(
                "Item presentation persistence is temporarily unavailable"
            ) from error

    async def find_current(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        kind: ItemPresentationKind,
        input_signature: RenderInputSignature,
    ) -> ItemPresentationAsset | None:
        async with self._sessions() as session:
            record = (
                await session.execute(
                    select(ItemPresentationAssetRecord).where(
                        ItemPresentationAssetRecord.user_id == user_id,
                        ItemPresentationAssetRecord.item_id == item_id,
                        ItemPresentationAssetRecord.kind == kind.value,
                        ItemPresentationAssetRecord.input_version == input_signature.version,
                        ItemPresentationAssetRecord.input_hash == input_signature.hash,
                    )
                )
            ).scalar_one_or_none()
            return _asset_from_record(record) if record is not None else None

    async def get_for_user(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
    ) -> ItemPresentationAsset | None:
        async with self._sessions() as session:
            record = (
                await session.execute(
                    select(ItemPresentationAssetRecord).where(
                        ItemPresentationAssetRecord.id == asset_id,
                        ItemPresentationAssetRecord.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
            return _asset_from_record(record) if record is not None else None


def _asset_values(asset: ItemPresentationAsset) -> dict[str, object | None]:
    return {
        "id": asset.id,
        "user_id": asset.user_id,
        "item_id": asset.item_id,
        "kind": asset.kind.value,
        "status": asset.status.value,
        "input_version": asset.input_signature.version,
        "input_hash": asset.input_signature.hash,
        "request_key": asset.request_key,
        "object_key": asset.output.object_key if asset.output is not None else None,
        "content_hash": asset.output.content_hash if asset.output is not None else None,
        "content_type": asset.output.content_type if asset.output is not None else None,
        "failure_code": asset.failure_code,
        "failure_message": asset.failure_message,
        "provider_trace": (
            {
                "provider": asset.provider_trace.provider,
                "model": asset.provider_trace.model,
                "parameters": dict(asset.provider_trace.parameters),
            }
            if asset.provider_trace is not None
            else None
        ),
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }


def _asset_from_record(record: ItemPresentationAssetRecord) -> ItemPresentationAsset:
    return ItemPresentationAsset(
        id=record.id,
        user_id=record.user_id,
        item_id=record.item_id,
        kind=ItemPresentationKind(record.kind),
        status=ItemPresentationStatus(record.status),
        input_signature=RenderInputSignature(
            version=record.input_version,
            hash=record.input_hash,
        ),
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


def _raise_on_idempotency_conflict(
    record: ItemPresentationAssetRecord,
    asset: ItemPresentationAsset,
) -> None:
    if (
        record.item_id != asset.item_id
        or record.kind != asset.kind.value
        or record.input_hash != asset.input_signature.hash
        or record.input_version != asset.input_signature.version
    ):
        raise ItemPresentationIdempotencyConflict(
            "Item presentation idempotency key was reused with different input"
        )


async def _find_equivalent(
    session: AsyncSession,
    asset: ItemPresentationAsset,
) -> ItemPresentationAssetRecord | None:
    return (
        await session.execute(
            select(ItemPresentationAssetRecord).where(
                ItemPresentationAssetRecord.user_id == asset.user_id,
                ItemPresentationAssetRecord.item_id == asset.item_id,
                ItemPresentationAssetRecord.kind == asset.kind.value,
                ItemPresentationAssetRecord.input_version == asset.input_signature.version,
                ItemPresentationAssetRecord.input_hash == asset.input_signature.hash,
            )
        )
    ).scalar_one_or_none()
