from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from math import isclose, sqrt
from types import MappingProxyType
from uuid import UUID, uuid4

from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSourceKind,
    OwnershipState,
    is_valid_selection_key,
)

WHOLE_CAPTURE_SELECTION_KEY = "whole_capture"


class FieldProvenance(StrEnum):
    MODEL = "model"
    USER = "user"
    CURATED_SEED = "curated_seed"


class ItemStatus(StrEnum):
    PROCESSING = "processing"
    PARTIAL = "partial"
    READY = "ready"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class FieldEnvelope:
    value: object
    provenance: FieldProvenance
    confidence: float
    model_version: str | None
    locked: bool

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.provenance is FieldProvenance.USER and not self.locked:
            raise ValueError("user-provided fields must be locked")


@dataclass(frozen=True, slots=True)
class ModelField:
    value: object
    confidence: float
    model_version: str

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.model_version.strip():
            raise ValueError("model_version must not be empty")


@dataclass(frozen=True, slots=True)
class ItemAttributes:
    fields: Mapping[str, FieldEnvelope] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))

    def merge_model(self, incoming: Mapping[str, ModelField]) -> ItemAttributes:
        merged = dict(self.fields)
        for name, model_field in incoming.items():
            current = merged.get(name)
            if current is not None and current.locked:
                continue
            merged[name] = FieldEnvelope(
                value=model_field.value,
                provenance=FieldProvenance.MODEL,
                confidence=model_field.confidence,
                model_version=model_field.model_version,
                locked=False,
            )
        return ItemAttributes(fields=merged)

    def with_user_value(self, name: str, value: object) -> ItemAttributes:
        if not name.strip():
            raise ValueError("attribute name must not be empty")
        updated = dict(self.fields)
        updated[name] = FieldEnvelope(
            value=value,
            provenance=FieldProvenance.USER,
            confidence=1,
            model_version=None,
            locked=True,
        )
        return ItemAttributes(updated)


@dataclass(frozen=True, slots=True)
class WardrobeItem:
    id: UUID
    user_id: UUID
    capture_id: UUID
    selection_key: str
    source_object_key: str
    source_available: bool
    source_kind: CaptureSourceKind
    ownership: OwnershipState
    status: ItemStatus
    attributes: ItemAttributes
    model_metadata: Mapping[str, object]
    embedding: tuple[float, ...] | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_metadata", MappingProxyType(dict(self.model_metadata)))
        if not is_valid_selection_key(self.selection_key):
            raise ValueError("selection key must be a 1-64 character ASCII alphanumeric identifier")
        if self.embedding is not None:
            if not self.embedding:
                raise ValueError("embedding must not be empty")
            norm = sqrt(sum(value * value for value in self.embedding))
            if not isclose(norm, 1, rel_tol=1e-5, abs_tol=1e-5):
                raise ValueError("embedding must be L2-normalized")

    @classmethod
    def processing(
        cls,
        capture: Capture,
        *,
        selection_key: str = WHOLE_CAPTURE_SELECTION_KEY,
    ) -> WardrobeItem:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=capture.user_id,
            capture_id=capture.id,
            selection_key=selection_key,
            source_object_key=capture.source.object_key,
            source_available=True,
            source_kind=capture.source.kind,
            ownership=capture.ownership,
            status=ItemStatus.PROCESSING,
            attributes=ItemAttributes(),
            model_metadata={},
            embedding=None,
            created_at=now,
            updated_at=now,
        )

    def with_attributes(self, attributes: ItemAttributes) -> WardrobeItem:
        return replace(self, attributes=attributes, updated_at=datetime.now(UTC))

    def apply_model(
        self,
        fields: Mapping[str, ModelField],
        metadata: Mapping[str, object],
    ) -> WardrobeItem:
        merged_metadata = dict(self.model_metadata)
        merged_metadata.update(metadata)
        return replace(
            self,
            status=ItemStatus.PROCESSING,
            attributes=self.attributes.merge_model(fields),
            model_metadata=merged_metadata,
            updated_at=datetime.now(UTC),
        )

    def with_embedding(
        self,
        embedding: tuple[float, ...],
        *,
        model_version: str,
    ) -> WardrobeItem:
        metadata = dict(self.model_metadata)
        metadata["embedding_model"] = model_version
        return replace(
            self,
            embedding=embedding,
            model_metadata=metadata,
            updated_at=datetime.now(UTC),
        )

    def with_status(self, status: ItemStatus) -> WardrobeItem:
        return replace(self, status=status, updated_at=datetime.now(UTC))

    def with_model_metadata(self, metadata: Mapping[str, object]) -> WardrobeItem:
        merged = dict(self.model_metadata)
        merged.update(metadata)
        return replace(
            self,
            model_metadata=merged,
            updated_at=datetime.now(UTC),
        )

    def with_source_deleted(self) -> WardrobeItem:
        return replace(self, source_available=False, updated_at=datetime.now(UTC))

    def with_ownership(self, ownership: OwnershipState) -> WardrobeItem:
        return replace(self, ownership=ownership, updated_at=datetime.now(UTC))

    def correct(self, name: str, value: object) -> WardrobeItem:
        return replace(
            self,
            attributes=self.attributes.with_user_value(name, value),
            updated_at=datetime.now(UTC),
        )
