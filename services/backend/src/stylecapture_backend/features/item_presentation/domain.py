from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from stylecapture_backend.features.render.domain import (
    RenderInputSignature,
    RenderOutput,
    RenderProviderTrace,
)


class ItemPresentationKind(StrEnum):
    PIXEL_ITEM = "pixel_item"
    FLAT_LAY_ITEM = "flat_lay_item"


class ItemPresentationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ItemPresentationAsset:
    id: UUID
    user_id: UUID
    item_id: UUID
    kind: ItemPresentationKind
    status: ItemPresentationStatus
    input_signature: RenderInputSignature
    request_key: str
    output: RenderOutput | None
    failure_code: str | None
    failure_message: str | None
    provider_trace: RenderProviderTrace | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        request_key = self.request_key.strip()
        if not 1 <= len(request_key) <= 128:
            raise ValueError("item presentation request key must contain 1 to 128 characters")
        object.__setattr__(self, "request_key", request_key)
        if self.status is ItemPresentationStatus.SUCCEEDED:
            if self.output is None:
                raise ValueError("succeeded item presentation must reference output")
        elif self.output is not None:
            raise ValueError("unfinished item presentation cannot reference output")
        if self.status is not ItemPresentationStatus.FAILED and self.failure_code is not None:
            raise ValueError("only failed item presentations may carry a failure code")
        if self.failure_code is not None and not self.failure_code.strip():
            raise ValueError("failure code must not be blank")
        if self.failure_message is not None and not self.failure_message.strip():
            raise ValueError("failure message must not be blank")

    @classmethod
    def queued(
        cls,
        *,
        user_id: UUID,
        item_id: UUID,
        kind: ItemPresentationKind,
        input_signature: RenderInputSignature,
        request_key: str,
    ) -> ItemPresentationAsset:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            item_id=item_id,
            kind=kind,
            status=ItemPresentationStatus.QUEUED,
            input_signature=input_signature,
            request_key=request_key,
            output=None,
            failure_code=None,
            failure_message=None,
            provider_trace=None,
            created_at=now,
            updated_at=now,
        )

    def mark_running(
        self,
        provider_trace: RenderProviderTrace | None = None,
    ) -> ItemPresentationAsset:
        return replace(
            self,
            status=ItemPresentationStatus.RUNNING,
            output=None,
            failure_code=None,
            failure_message=None,
            provider_trace=provider_trace or self.provider_trace,
            updated_at=datetime.now(UTC),
        )

    def mark_succeeded(
        self,
        *,
        output: RenderOutput,
        provider_trace: RenderProviderTrace,
    ) -> ItemPresentationAsset:
        return replace(
            self,
            status=ItemPresentationStatus.SUCCEEDED,
            output=output,
            failure_code=None,
            failure_message=None,
            provider_trace=provider_trace,
            updated_at=datetime.now(UTC),
        )

    def mark_failed(self, *, code: str, message: str) -> ItemPresentationAsset:
        return replace(
            self,
            status=ItemPresentationStatus.FAILED,
            output=None,
            failure_code=code.strip(),
            failure_message=message.strip(),
            updated_at=datetime.now(UTC),
        )

    def retry(self) -> ItemPresentationAsset:
        if self.status in {ItemPresentationStatus.QUEUED, ItemPresentationStatus.RUNNING}:
            return self
        return replace(
            self,
            status=ItemPresentationStatus.QUEUED,
            output=None,
            failure_code=None,
            failure_message=None,
            provider_trace=None,
            updated_at=datetime.now(UTC),
        )
