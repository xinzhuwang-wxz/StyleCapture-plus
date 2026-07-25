from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID, uuid4


class RenderArtifactKind(StrEnum):
    COLLAGE = "collage"
    TRY_ON = "try_on"
    PIXEL_COVER = "pixel_cover"


class RenderArtifactStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEGRADED = "degraded"


class RenderPrivacy(StrEnum):
    PRIVATE = "private"
    SHAREABLE_PIXEL = "shareable_pixel"


@dataclass(frozen=True, slots=True)
class RenderInputSignature:
    version: str
    hash: str

    def __post_init__(self) -> None:
        normalized_version = self.version.strip()
        if not 1 <= len(normalized_version) <= 80:
            raise ValueError("render input version must contain between 1 and 80 characters")
        if len(self.hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.hash
        ):
            raise ValueError("render input hash must be lowercase SHA-256")
        object.__setattr__(self, "version", normalized_version)


@dataclass(frozen=True, slots=True)
class RenderOutput:
    object_key: str
    content_hash: str
    content_type: str

    def __post_init__(self) -> None:
        normalized_key = self.object_key.strip()
        if (
            not normalized_key
            or len(normalized_key) > 512
            or not normalized_key.startswith("derived/")
            or ".." in normalized_key.split("/")
            or "\\" in normalized_key
        ):
            raise ValueError("render object key must be a derived object key")
        if len(self.content_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.content_hash
        ):
            raise ValueError("render content hash must be lowercase SHA-256")
        if self.content_type not in {"image/png", "image/webp", "image/jpeg"}:
            raise ValueError("render content type must be PNG, WebP, or JPEG")
        object.__setattr__(self, "object_key", normalized_key)


@dataclass(frozen=True, slots=True)
class RenderProviderTrace:
    provider: str
    model: str
    parameters: Mapping[str, object]

    def __post_init__(self) -> None:
        provider = self.provider.strip()
        model = self.model.strip()
        if not 1 <= len(provider) <= 120:
            raise ValueError("render provider trace provider must not be empty")
        if not 1 <= len(model) <= 160:
            raise ValueError("render provider trace model must not be empty")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True)
class RenderArtifact:
    id: UUID
    user_id: UUID
    look_id: UUID
    kind: RenderArtifactKind
    status: RenderArtifactStatus
    input_signature: RenderInputSignature
    request_key: str
    privacy: RenderPrivacy
    output: RenderOutput | None
    source_artifact_id: UUID | None
    fallback_artifact_id: UUID | None
    failure_code: str | None
    failure_message: str | None
    provider_trace: RenderProviderTrace | None
    created_at: datetime
    updated_at: datetime
    subject_object_key: str | None = None

    def __post_init__(self) -> None:
        request_key = self.request_key.strip()
        if not 1 <= len(request_key) <= 128:
            raise ValueError("render request key must contain between 1 and 128 characters")
        object.__setattr__(self, "request_key", request_key)
        if self.status in {RenderArtifactStatus.SUCCEEDED, RenderArtifactStatus.DEGRADED}:
            if self.output is None:
                raise ValueError("successful or degraded render artifacts must reference output")
        elif self.output is not None:
            raise ValueError("queued, running, or failed render artifacts cannot reference output")
        if self.status is RenderArtifactStatus.DEGRADED and self.fallback_artifact_id is None:
            raise ValueError("degraded render artifacts must reference their fallback artifact")
        if self.status is not RenderArtifactStatus.FAILED and self.failure_code is not None:
            raise ValueError("only failed render artifacts may carry a failure code")
        if self.failure_code is not None and not self.failure_code.strip():
            raise ValueError("failure code must not be blank")
        if self.failure_message is not None and not self.failure_message.strip():
            raise ValueError("failure message must not be blank")
        if (
            self.privacy is RenderPrivacy.SHAREABLE_PIXEL
            and self.kind is not RenderArtifactKind.PIXEL_COVER
        ):
            raise ValueError("only pixel cover render artifacts may be public-share eligible")
        if self.subject_object_key is not None:
            subject_key = self.subject_object_key.strip()
            if (
                self.kind is not RenderArtifactKind.TRY_ON
                or not subject_key.startswith("originals/")
                or len(subject_key) > 512
                or ".." in subject_key.split("/")
                or "\\" in subject_key
            ):
                raise ValueError("try-on subject must be a private original image")
            object.__setattr__(self, "subject_object_key", subject_key)

    @classmethod
    def queued(
        cls,
        *,
        user_id: UUID,
        look_id: UUID,
        kind: RenderArtifactKind,
        input_signature: RenderInputSignature,
        request_key: str,
        privacy: RenderPrivacy = RenderPrivacy.PRIVATE,
        source_artifact_id: UUID | None = None,
        provider_trace: RenderProviderTrace | None = None,
        subject_object_key: str | None = None,
    ) -> RenderArtifact:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            look_id=look_id,
            kind=kind,
            status=RenderArtifactStatus.QUEUED,
            input_signature=input_signature,
            request_key=request_key,
            privacy=privacy,
            output=None,
            source_artifact_id=source_artifact_id,
            fallback_artifact_id=None,
            failure_code=None,
            failure_message=None,
            provider_trace=provider_trace,
            created_at=now,
            updated_at=now,
            subject_object_key=subject_object_key,
        )

    @property
    def share_eligible(self) -> bool:
        return (
            self.kind is RenderArtifactKind.PIXEL_COVER
            and self.privacy is RenderPrivacy.SHAREABLE_PIXEL
            and self.status is RenderArtifactStatus.SUCCEEDED
            and self.output is not None
        )

    def mark_running(
        self,
        *,
        provider_trace: RenderProviderTrace | None = None,
    ) -> RenderArtifact:
        return replace(
            self,
            status=RenderArtifactStatus.RUNNING,
            output=None,
            failure_code=None,
            failure_message=None,
            provider_trace=provider_trace or self.provider_trace,
            updated_at=datetime.now(UTC),
        )

    def mark_succeeded(self, output: RenderOutput) -> RenderArtifact:
        return replace(
            self,
            status=RenderArtifactStatus.SUCCEEDED,
            output=output,
            fallback_artifact_id=None,
            failure_code=None,
            failure_message=None,
            updated_at=datetime.now(UTC),
        )

    def forget_subject_photo(self) -> RenderArtifact:
        if self.kind is not RenderArtifactKind.TRY_ON:
            raise ValueError("only try-on artifacts can forget a subject photo")
        return replace(
            self,
            subject_object_key=None,
            updated_at=datetime.now(UTC),
        )

    def mark_failed(self, *, code: str, message: str) -> RenderArtifact:
        return replace(
            self,
            status=RenderArtifactStatus.FAILED,
            output=None,
            failure_code=code.strip(),
            failure_message=message.strip(),
            updated_at=datetime.now(UTC),
        )

    def mark_degraded_to(self, *, fallback: RenderArtifact, reason: str) -> RenderArtifact:
        if fallback.output is None:
            raise ValueError("render fallback must have a stored output")
        if fallback.look_id != self.look_id or fallback.user_id != self.user_id:
            raise ValueError("render fallback must belong to the same user's Look")
        return replace(
            self,
            status=RenderArtifactStatus.DEGRADED,
            output=fallback.output,
            fallback_artifact_id=fallback.id,
            failure_code=None,
            failure_message=reason.strip(),
            updated_at=datetime.now(UTC),
        )
