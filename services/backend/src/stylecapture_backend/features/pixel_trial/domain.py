from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from stylecapture_backend.features.render.domain import RenderOutput, RenderProviderTrace


class PixelTrialStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PixelTrial:
    id: UUID
    user_id: UUID
    status: PixelTrialStatus
    subject_object_key: str | None
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
            raise ValueError("pixel trial request key must contain between 1 and 128 characters")
        object.__setattr__(self, "request_key", request_key)
        if self.subject_object_key is not None:
            subject = self.subject_object_key.strip()
            if (
                not subject.startswith("originals/")
                or len(subject) > 512
                or ".." in subject.split("/")
                or "\\" in subject
            ):
                raise ValueError("pixel trial subject must be a private original image")
            object.__setattr__(self, "subject_object_key", subject)
        if self.status is PixelTrialStatus.SUCCEEDED:
            if self.output is None:
                raise ValueError("succeeded pixel trial must reference output")
        elif self.output is not None:
            raise ValueError("unfinished pixel trial cannot reference output")
        if self.status is not PixelTrialStatus.FAILED and self.failure_code is not None:
            raise ValueError("only failed pixel trials may carry a failure code")
        if self.failure_code is not None and not self.failure_code.strip():
            raise ValueError("failure code must not be blank")
        if self.failure_message is not None and not self.failure_message.strip():
            raise ValueError("failure message must not be blank")

    @classmethod
    def queued(
        cls,
        *,
        user_id: UUID,
        subject_object_key: str,
        request_key: str,
    ) -> PixelTrial:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            status=PixelTrialStatus.QUEUED,
            subject_object_key=subject_object_key,
            request_key=request_key,
            output=None,
            failure_code=None,
            failure_message=None,
            provider_trace=None,
            created_at=now,
            updated_at=now,
        )

    def mark_running(self, provider_trace: RenderProviderTrace | None = None) -> PixelTrial:
        return replace(
            self,
            status=PixelTrialStatus.RUNNING,
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
    ) -> PixelTrial:
        return replace(
            self,
            status=PixelTrialStatus.SUCCEEDED,
            output=output,
            failure_code=None,
            failure_message=None,
            provider_trace=provider_trace,
            updated_at=datetime.now(UTC),
        )

    def mark_failed(self, *, code: str, message: str) -> PixelTrial:
        return replace(
            self,
            status=PixelTrialStatus.FAILED,
            output=None,
            failure_code=code.strip(),
            failure_message=message.strip(),
            updated_at=datetime.now(UTC),
        )

    def forget_subject_photo(self) -> PixelTrial:
        return replace(self, subject_object_key=None, updated_at=datetime.now(UTC))
