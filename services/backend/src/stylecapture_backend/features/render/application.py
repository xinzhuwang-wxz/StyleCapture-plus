from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderArtifactStatus,
    RenderInputSignature,
    RenderOutput,
    RenderPrivacy,
    RenderProviderTrace,
)
from stylecapture_backend.features.render.ports import (
    RenderArtifactNotFound,
    RenderArtifactRepository,
)


@dataclass(frozen=True, slots=True)
class RenderArtifactView:
    id: UUID
    user_id: UUID
    look_id: UUID
    kind: RenderArtifactKind
    status: RenderArtifactStatus
    input_version: str
    input_hash: str
    request_key: str
    object_key: str | None
    content_hash: str | None
    content_type: str | None
    source_artifact_id: UUID | None
    fallback_artifact_id: UUID | None
    failure_code: str | None
    failure_message: str | None
    share_eligible: bool
    created_at: datetime
    updated_at: datetime
    subject_object_key: str | None
    subject_used: bool
    dispatch_required: bool = False
    cache_hit: bool = False


class RenderApplication:
    def __init__(self, *, artifacts: RenderArtifactRepository) -> None:
        self._artifacts = artifacts

    async def create_or_get(
        self,
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
    ) -> RenderArtifactView:
        cached = await self._artifacts.find_cache_hit(
            look_id=look_id,
            kind=kind,
            input_signature=input_signature,
        )
        if cached is not None and cached.user_id == user_id:
            return _view(cached, cache_hit=True)
        artifact = RenderArtifact.queued(
            user_id=user_id,
            look_id=look_id,
            kind=kind,
            input_signature=input_signature,
            request_key=request_key,
            privacy=privacy,
            source_artifact_id=source_artifact_id,
            provider_trace=provider_trace,
            subject_object_key=subject_object_key,
        )
        stored = await self._artifacts.ensure_requested(artifact)
        return _view(
            stored,
            cache_hit=stored.status is RenderArtifactStatus.SUCCEEDED,
            # A queued artifact may have survived a transient broker failure. Re-dispatching
            # the same artifact is safe because processing and state transitions are idempotent.
            dispatch_required=stored.status is RenderArtifactStatus.QUEUED,
        )

    async def list_for_look(self, *, user_id: UUID, look_id: UUID) -> list[RenderArtifactView]:
        return [
            _view(artifact)
            for artifact in await self._artifacts.list_for_look(user_id=user_id, look_id=look_id)
        ]

    async def get(self, *, user_id: UUID, artifact_id: UUID) -> RenderArtifactView:
        artifact = await self._artifacts.get_for_user(user_id=user_id, artifact_id=artifact_id)
        if artifact is None:
            raise RenderArtifactNotFound("Render artifact not found")
        return _view(artifact)

    async def forget_subject_photo(
        self,
        *,
        user_id: UUID,
        artifact_id: UUID,
    ) -> RenderArtifactView:
        artifact = await self._require_artifact(
            user_id=user_id,
            artifact_id=artifact_id,
        )
        return _view(await self._artifacts.save(artifact.forget_subject_photo()))

    async def mark_running(
        self,
        *,
        user_id: UUID,
        artifact_id: UUID,
        provider_trace: RenderProviderTrace | None = None,
    ) -> RenderArtifactView:
        artifact = await self._require_artifact(user_id=user_id, artifact_id=artifact_id)
        return _view(
            await self._artifacts.save(artifact.mark_running(provider_trace=provider_trace))
        )

    async def mark_succeeded(
        self,
        *,
        user_id: UUID,
        artifact_id: UUID,
        output: RenderOutput,
    ) -> RenderArtifactView:
        artifact = await self._require_artifact(user_id=user_id, artifact_id=artifact_id)
        return _view(await self._artifacts.save(artifact.mark_succeeded(output)))

    async def mark_failed(
        self,
        *,
        user_id: UUID,
        artifact_id: UUID,
        code: str,
        message: str,
    ) -> RenderArtifactView:
        artifact = await self._require_artifact(user_id=user_id, artifact_id=artifact_id)
        return _view(await self._artifacts.save(artifact.mark_failed(code=code, message=message)))

    async def degrade_to_fallback(
        self,
        *,
        user_id: UUID,
        artifact_id: UUID,
        fallback_artifact_id: UUID,
        reason: str,
    ) -> RenderArtifactView:
        artifact = await self._require_artifact(user_id=user_id, artifact_id=artifact_id)
        fallback = await self._require_artifact(user_id=user_id, artifact_id=fallback_artifact_id)
        return _view(
            await self._artifacts.save(artifact.mark_degraded_to(fallback=fallback, reason=reason))
        )

    async def _require_artifact(self, *, user_id: UUID, artifact_id: UUID) -> RenderArtifact:
        artifact = await self._artifacts.get_for_user(user_id=user_id, artifact_id=artifact_id)
        if artifact is None:
            raise RenderArtifactNotFound("Render artifact not found")
        return artifact


def _view(
    artifact: RenderArtifact,
    *,
    cache_hit: bool = False,
    dispatch_required: bool = False,
) -> RenderArtifactView:
    return RenderArtifactView(
        id=artifact.id,
        user_id=artifact.user_id,
        look_id=artifact.look_id,
        kind=artifact.kind,
        status=artifact.status,
        input_version=artifact.input_signature.version,
        input_hash=artifact.input_signature.hash,
        request_key=artifact.request_key,
        object_key=artifact.output.object_key if artifact.output is not None else None,
        content_hash=artifact.output.content_hash if artifact.output is not None else None,
        content_type=artifact.output.content_type if artifact.output is not None else None,
        source_artifact_id=artifact.source_artifact_id,
        fallback_artifact_id=artifact.fallback_artifact_id,
        failure_code=artifact.failure_code,
        failure_message=artifact.failure_message,
        share_eligible=artifact.share_eligible,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
        subject_object_key=artifact.subject_object_key,
        subject_used=bool(
            artifact.provider_trace is not None
            and artifact.provider_trace.parameters.get("personalization") == "user_photo"
        ),
        dispatch_required=dispatch_required,
        cache_hit=cache_hit,
    )
