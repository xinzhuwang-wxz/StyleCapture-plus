from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stylecapture_backend.features.capture.domain import OwnershipState
from stylecapture_backend.features.wardrobe.domain import (
    FieldEnvelope,
    FieldProvenance,
    ItemAttributes,
    ItemStatus,
    WardrobeItem,
)
from stylecapture_backend.features.wardrobe.infrastructure.models import ItemRecord


class SqlAlchemyWardrobeRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_by_capture(self, capture_id: UUID) -> WardrobeItem | None:
        async with self._sessions() as session:
            statement = select(ItemRecord).where(ItemRecord.capture_id == capture_id)
            record = (await session.execute(statement)).scalar_one_or_none()
            return _item_from_record(record) if record is not None else None

    async def save(self, item: WardrobeItem) -> WardrobeItem:
        async with self._sessions() as session:
            await session.merge(_item_record(item))
            await session.commit()
        return item


def _item_record(item: WardrobeItem) -> ItemRecord:
    return ItemRecord(
        id=item.id,
        user_id=item.user_id,
        capture_id=item.capture_id,
        source_object_key=item.source_object_key,
        ownership=item.ownership.value,
        status=item.status.value,
        category=_text_field(item.attributes, "category"),
        subcategory=_text_field(item.attributes, "subcategory"),
        description=_text_field(item.attributes, "description"),
        attributes=_attributes_to_json(item.attributes),
        model_metadata=dict(item.model_metadata),
        embedding=list(item.embedding) if item.embedding is not None else None,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _item_from_record(record: ItemRecord) -> WardrobeItem:
    embedding = (
        tuple(float(value) for value in record.embedding) if record.embedding is not None else None
    )
    return WardrobeItem(
        id=record.id,
        user_id=record.user_id,
        capture_id=record.capture_id,
        source_object_key=record.source_object_key,
        ownership=OwnershipState(record.ownership),
        status=ItemStatus(record.status),
        attributes=_attributes_from_json(record.attributes),
        model_metadata=record.model_metadata,
        embedding=embedding,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _attributes_to_json(attributes: ItemAttributes) -> dict[str, object]:
    return {
        name: {
            "value": field.value,
            "provenance": field.provenance.value,
            "confidence": field.confidence,
            "model_version": field.model_version,
            "locked": field.locked,
        }
        for name, field in attributes.fields.items()
    }


def _attributes_from_json(payload: dict[str, object]) -> ItemAttributes:
    fields: dict[str, FieldEnvelope] = {}
    for name, raw_value in payload.items():
        if not isinstance(raw_value, dict):
            raise ValueError(f"stored attribute {name} is not an object")
        value: dict[str, Any] = raw_value
        fields[name] = FieldEnvelope(
            value=value.get("value"),
            provenance=FieldProvenance(str(value["provenance"])),
            confidence=float(value["confidence"]),
            model_version=(
                str(value["model_version"]) if value.get("model_version") is not None else None
            ),
            locked=bool(value["locked"]),
        )
    return ItemAttributes(fields)


def _text_field(attributes: ItemAttributes, name: str) -> str | None:
    field = attributes.fields.get(name)
    return str(field.value) if field is not None else None
