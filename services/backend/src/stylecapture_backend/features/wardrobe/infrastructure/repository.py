from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stylecapture_backend.features.capture.domain import CaptureSourceKind, OwnershipState
from stylecapture_backend.features.capture.infrastructure.models import CaptureRecord
from stylecapture_backend.features.look.infrastructure.models import (
    LookComponentRecord,
    LookRecord,
)
from stylecapture_backend.features.outfit.domain import (
    OutfitCategory,
    OutfitRecallRequirements,
)
from stylecapture_backend.features.render.infrastructure.models import RenderArtifactRecord
from stylecapture_backend.features.wardrobe.domain import (
    WHOLE_CAPTURE_SELECTION_KEY,
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

    async def get_by_capture(
        self,
        capture_id: UUID,
        selection_key: str = WHOLE_CAPTURE_SELECTION_KEY,
    ) -> WardrobeItem | None:
        async with self._sessions() as session:
            statement = (
                select(ItemRecord, CaptureRecord.source_kind)
                .join(CaptureRecord, CaptureRecord.id == ItemRecord.capture_id)
                .where(
                    ItemRecord.capture_id == capture_id,
                    ItemRecord.selection_key == selection_key,
                )
            )
            row = (await session.execute(statement)).one_or_none()
            return _item_from_record(row[0], row[1]) if row is not None else None

    async def list_for_user(self, user_id: UUID) -> list[WardrobeItem]:
        async with self._sessions() as session:
            statement = (
                select(ItemRecord, CaptureRecord.source_kind)
                .join(CaptureRecord, CaptureRecord.id == ItemRecord.capture_id)
                .where(ItemRecord.user_id == user_id)
                .order_by(ItemRecord.created_at.desc())
                .limit(100)
            )
            rows = (await session.execute(statement)).all()
            return [_item_from_record(row[0], row[1]) for row in rows]

    async def recall_for_outfit(
        self,
        *,
        user_id: UUID,
        requirements: OutfitRecallRequirements,
    ) -> list[WardrobeItem]:
        """Recall real wardrobe assets before deterministic rule scoring.

        SQL owns the stable owned-before-inspiration priority. When an anchored item
        has a provider embedding, pgvector cosine distance provides the tie-breaker;
        items without vectors remain eligible and are ranked by tags in the
        application layer. Commerce is intentionally absent from this repository:
        unfilled slots become explicit search demands rather than invented products.
        """

        async with self._sessions() as session:
            anchor_embedding: list[float] | None = None
            if requirements.anchor_item_id is not None:
                anchor_embedding = (
                    await session.execute(
                        select(ItemRecord.embedding).where(
                            ItemRecord.id == requirements.anchor_item_id,
                            ItemRecord.user_id == user_id,
                        )
                    )
                ).scalar_one_or_none()
            ownership_order = case(
                (ItemRecord.ownership == OwnershipState.OWNED.value, 0),
                else_=1,
            )
            ordering: list[Any] = [ownership_order]
            if anchor_embedding is not None:
                ordering.append(ItemRecord.embedding.cosine_distance(anchor_embedding).nulls_last())
            ordering.extend((ItemRecord.category, ItemRecord.created_at.desc(), ItemRecord.id))
            categories = _recall_category_values(requirements.required_roles)
            filters = [
                ItemRecord.user_id == user_id,
                ItemRecord.status.in_((ItemStatus.READY.value, ItemStatus.PARTIAL.value)),
                ItemRecord.ownership.in_(
                    (OwnershipState.OWNED.value, OwnershipState.INSPIRATION.value)
                ),
                ItemRecord.category.in_(categories),
            ]
            if requirements.exclude_item_ids:
                filters.append(ItemRecord.id.not_in(requirements.exclude_item_ids))
            statement = (
                select(ItemRecord, CaptureRecord.source_kind)
                .join(CaptureRecord, CaptureRecord.id == ItemRecord.capture_id)
                .where(*filters)
                .order_by(*ordering)
                .limit(120)
            )
            rows = (await session.execute(statement)).all()
            return [_item_from_record(row[0], row[1]) for row in rows]

    async def get_for_user(self, item_id: UUID, user_id: UUID) -> WardrobeItem | None:
        async with self._sessions() as session:
            statement = (
                select(ItemRecord, CaptureRecord.source_kind)
                .join(CaptureRecord, CaptureRecord.id == ItemRecord.capture_id)
                .where(ItemRecord.id == item_id, ItemRecord.user_id == user_id)
            )
            row = (await session.execute(statement)).one_or_none()
            return _item_from_record(row[0], row[1]) if row is not None else None

    async def save(self, item: WardrobeItem) -> WardrobeItem:
        async with self._sessions() as session:
            existing = (
                await session.execute(
                    select(ItemRecord)
                    .where(
                        or_(
                            ItemRecord.id == item.id,
                            (
                                (ItemRecord.capture_id == item.capture_id)
                                & (ItemRecord.selection_key == item.selection_key)
                            ),
                        )
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            incoming = _item_record(item)
            if existing is None:
                session.add(incoming)
            else:
                attributes = _merge_worker_attributes(existing.attributes, incoming.attributes)
                existing.source_available = existing.source_available and incoming.source_available
                if incoming.display_object_key is not None:
                    existing.display_object_key = incoming.display_object_key
                existing.status = incoming.status
                existing.category = _json_text_field(attributes, "category")
                existing.subcategory = _json_text_field(attributes, "subcategory")
                existing.description = _json_text_field(attributes, "description")
                existing.attributes = attributes
                existing.model_metadata = {
                    **existing.model_metadata,
                    **incoming.model_metadata,
                }
                if incoming.embedding is not None:
                    existing.embedding = incoming.embedding
                existing.updated_at = incoming.updated_at
            await session.commit()
        stored = await self.get_by_capture(item.capture_id, item.selection_key)
        if stored is None:
            raise RuntimeError("saved wardrobe item could not be reloaded")
        return stored

    async def save_user_state(self, item: WardrobeItem) -> WardrobeItem:
        async with self._sessions() as session:
            existing = (
                await session.execute(
                    select(ItemRecord)
                    .where(
                        ItemRecord.id == item.id,
                        ItemRecord.user_id == item.user_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if existing is None:
                raise LookupError(item.id)

            incoming_attributes = _attributes_to_json(item.attributes)
            attributes = _merge_user_attributes(
                existing.attributes,
                incoming_attributes,
            )
            existing.ownership = item.ownership.value
            existing.source_available = existing.source_available and item.source_available
            existing.category = _json_text_field(attributes, "category")
            existing.subcategory = _json_text_field(attributes, "subcategory")
            existing.description = _json_text_field(attributes, "description")
            existing.attributes = attributes
            existing.updated_at = item.updated_at
            if not item.source_available:
                await session.execute(
                    update(ItemRecord)
                    .where(ItemRecord.capture_id == item.capture_id)
                    .values(
                        source_available=False,
                        updated_at=item.updated_at,
                    )
                )
            await session.commit()

        stored = await self.get_by_capture(item.capture_id, item.selection_key)
        if stored is None:
            raise RuntimeError("saved wardrobe item could not be reloaded")
        return stored

    async def set_ownership_in_transaction(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        item_id: UUID,
        ownership: OwnershipState,
        updated_at: datetime,
    ) -> bool:
        """Update ownership within an existing persistence transaction."""

        record = (
            await session.execute(
                select(ItemRecord)
                .where(
                    ItemRecord.id == item_id,
                    ItemRecord.user_id == user_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if record is None:
            return False
        record.ownership = ownership.value
        record.updated_at = updated_at
        return True

    async def delete_for_user(self, item_id: UUID, user_id: UUID) -> bool:
        """Remove an item and every outfit-component reference to it atomically."""

        async with self._sessions() as session:
            item = (
                await session.execute(
                    select(ItemRecord)
                    .where(ItemRecord.id == item_id, ItemRecord.user_id == user_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if item is None:
                return False

            affected_look_ids = tuple(
                dict.fromkeys(
                    await session.scalars(
                        select(LookComponentRecord.look_id).where(
                            LookComponentRecord.item_id == item_id
                        )
                    )
                )
            )
            await session.execute(
                delete(LookComponentRecord).where(LookComponentRecord.item_id == item_id)
            )
            if affected_look_ids:
                # A generated cover can contain the removed item. Invalidate it
                # so clients do not continue presenting stale wardrobe data.
                await session.execute(
                    update(LookRecord)
                    .where(
                        LookRecord.id.in_(affected_look_ids),
                        LookRecord.user_id == user_id,
                    )
                    .values(status="partial", display_object_key=None)
                )
                # Generated collages/covers can still contain the removed item.
                # Remove their database presentations so render reads cannot
                # surface stale wardrobe state. Output blobs are retained for
                # the deployment's normal object-retention cleanup.
                await session.execute(
                    delete(RenderArtifactRecord).where(
                        RenderArtifactRecord.look_id.in_(affected_look_ids),
                        RenderArtifactRecord.fallback_artifact_id.is_not(None),
                    )
                )
                await session.execute(
                    delete(RenderArtifactRecord).where(
                        RenderArtifactRecord.look_id.in_(affected_look_ids)
                    )
                )
            await session.delete(item)
            await session.commit()
            return True


def _item_record(item: WardrobeItem) -> ItemRecord:
    return ItemRecord(
        id=item.id,
        user_id=item.user_id,
        capture_id=item.capture_id,
        selection_key=item.selection_key,
        source_object_key=item.source_object_key,
        display_object_key=item.display_object_key,
        source_available=item.source_available,
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


def _item_from_record(record: ItemRecord, source_kind: str) -> WardrobeItem:
    embedding = (
        tuple(float(value) for value in record.embedding) if record.embedding is not None else None
    )
    return WardrobeItem(
        id=record.id,
        user_id=record.user_id,
        capture_id=record.capture_id,
        selection_key=record.selection_key,
        source_object_key=record.source_object_key,
        display_object_key=record.display_object_key,
        source_available=record.source_available,
        source_kind=CaptureSourceKind(source_kind),
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


def _recall_category_values(
    roles: tuple[OutfitCategory, ...],
) -> tuple[str, ...]:
    values: list[str] = []
    for role in roles:
        candidates = (
            ("accessories", "bags", "headwear")
            if role is OutfitCategory.ACCESSORY
            else (role.value,)
        )
        for value in candidates:
            if value not in values:
                values.append(value)
    return tuple(values)


def _json_text_field(attributes: dict[str, object], name: str) -> str | None:
    field = attributes.get(name)
    if not isinstance(field, dict) or field.get("value") is None:
        return None
    return str(field["value"])


def _merge_worker_attributes(
    current: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    merged = dict(current)
    for name, value in incoming.items():
        current_value = current.get(name)
        if isinstance(current_value, dict) and current_value.get("locked") is True:
            continue
        merged[name] = value
    return merged


def _merge_user_attributes(
    current: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    merged = dict(current)
    for name, value in incoming.items():
        if (
            isinstance(value, dict)
            and value.get("provenance") == FieldProvenance.USER.value
            and value.get("locked") is True
        ):
            merged[name] = value
    return merged
