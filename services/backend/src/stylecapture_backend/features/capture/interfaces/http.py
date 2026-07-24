from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    CaptureError,
    SubmitCaptureCommand,
)
from stylecapture_backend.features.capture.domain import (
    CaptureSourceKind,
    JobState,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.ports import (
    JobRepository,
    ObjectStore,
    UploadRequest,
)
from stylecapture_backend.platform.errors import STABLE_ERROR_RESPONSES


class PrepareUploadBody(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    byte_size: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)


class PreparedUploadResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_at: datetime


class StoredObjectResponse(BaseModel):
    object_key: str
    content_type: str
    byte_size: int
    sha256: str
    width: int
    height: int


class SubmitCaptureBody(BaseModel):
    object_key: str = Field(min_length=1, max_length=512)
    sha256: str = Field(min_length=64, max_length=64)
    source_kind: CaptureSourceKind
    ownership: OwnershipState


class CaptureAcceptedResponse(BaseModel):
    capture_id: UUID
    job_id: UUID
    state: JobState
    status_url: str
    events_url: str


class JobResponse(BaseModel):
    job_id: UUID
    capture_id: UUID
    state: JobState
    attempt: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, job: ProcessingJob) -> JobResponse:
        return cls(
            job_id=job.id,
            capture_id=job.capture_id,
            state=job.state,
            attempt=job.attempt,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


@dataclass(frozen=True, slots=True)
class CaptureHttpServices:
    capture: CaptureApplication
    jobs: JobRepository
    objects: ObjectStore


def build_capture_router(
    services: CaptureHttpServices,
    *,
    sse_poll_interval: float,
    max_upload_bytes: int,
) -> APIRouter:
    router = APIRouter(prefix="/v1")

    @router.post(
        "/uploads/prepare",
        response_model=PreparedUploadResponse,
        status_code=status.HTTP_201_CREATED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def prepare_upload(body: PrepareUploadBody) -> PreparedUploadResponse:
        prepared = services.objects.prepare_upload(
            UploadRequest(
                file_name=body.file_name,
                content_type=body.content_type,
                byte_size=body.byte_size,
                sha256=body.sha256,
            )
        )
        return PreparedUploadResponse(
            upload_url=prepared.upload_url,
            object_key=prepared.object_key,
            expires_at=prepared.expires_at,
        )

    @router.put(
        "/uploads/{token}",
        response_model=StoredObjectResponse,
        status_code=status.HTTP_201_CREATED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def upload_object(
        token: str,
        request: Request,
        content_type: Annotated[str, Header(alias="Content-Type")],
        content_length: Annotated[int | None, Header(alias="Content-Length")] = None,
    ) -> StoredObjectResponse:
        if content_length is not None and content_length > max_upload_bytes:
            raise CaptureError(
                "upload_size_invalid",
                f"Image size must be between 1 and {max_upload_bytes} bytes",
                details={"max_bytes": max_upload_bytes},
            )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > max_upload_bytes:
                raise CaptureError(
                    "upload_size_invalid",
                    f"Image size must be between 1 and {max_upload_bytes} bytes",
                    details={"max_bytes": max_upload_bytes},
                )
        stored = services.objects.accept_upload(
            token,
            body=bytes(body),
            content_type=content_type,
        )
        return StoredObjectResponse(
            object_key=stored.object_key,
            content_type=stored.content_type,
            byte_size=stored.byte_size,
            sha256=stored.sha256,
            width=stored.width,
            height=stored.height,
        )

    @router.post(
        "/captures",
        response_model=CaptureAcceptedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def submit_capture(
        body: SubmitCaptureBody,
        user_id: Annotated[UUID, Header(alias="X-StyleCapture-User")],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> CaptureAcceptedResponse:
        submission = await services.capture.submit(
            SubmitCaptureCommand(
                user_id=user_id,
                object_key=body.object_key,
                sha256=body.sha256,
                source_kind=body.source_kind,
                ownership=body.ownership,
                idempotency_key=idempotency_key,
            )
        )
        return CaptureAcceptedResponse(
            capture_id=submission.capture.id,
            job_id=submission.job.id,
            state=submission.job.state,
            status_url=f"/v1/jobs/{submission.job.id}",
            events_url=f"/v1/jobs/{submission.job.id}/events",
        )

    @router.get(
        "/jobs/{job_id}",
        response_model=JobResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def get_job(
        job_id: UUID,
        user_id: Annotated[UUID, Header(alias="X-StyleCapture-User")],
    ) -> JobResponse:
        job = await services.jobs.get_for_user(job_id, user_id)
        if job is None:
            raise JobNotFoundError
        return JobResponse.from_domain(job)

    @router.get(
        "/jobs/{job_id}/events",
        responses=STABLE_ERROR_RESPONSES,
    )
    async def job_events(
        job_id: UUID,
        user_id: Annotated[UUID, Header(alias="X-StyleCapture-User")],
    ) -> StreamingResponse:
        initial_job = await services.jobs.get_for_user(job_id, user_id)
        if initial_job is None:
            raise JobNotFoundError

        async def stream() -> AsyncIterator[str]:
            previous_updated_at: datetime | None = None
            while True:
                job = await services.jobs.get_for_user(job_id, user_id)
                if job is None:
                    return
                if job.updated_at != previous_updated_at:
                    payload = JobResponse.from_domain(job).model_dump(mode="json")
                    yield f"event: job\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
                    previous_updated_at = job.updated_at
                if job.state in {JobState.PARTIAL, JobState.READY, JobState.ERROR}:
                    return
                await asyncio.sleep(sse_poll_interval)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router


class JobNotFoundError(LookupError):
    pass
