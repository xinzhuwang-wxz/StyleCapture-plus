from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware

from stylecapture_backend.features.capture.application import CaptureApplication, CaptureError
from stylecapture_backend.features.capture.interfaces.http import (
    CaptureHttpServices,
    JobNotFoundError,
    build_capture_router,
)
from stylecapture_backend.features.capture.ports import JobRepository, ObjectStore
from stylecapture_backend.platform.errors import ErrorBody, ErrorEnvelope


@dataclass(frozen=True, slots=True)
class BackendServices:
    capture: CaptureApplication
    jobs: JobRepository
    objects: ObjectStore


CAPTURE_ERROR_STATUS = {
    "unsupported_image_type": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    "upload_size_invalid": status.HTTP_413_CONTENT_TOO_LARGE,
    "upload_token_expired": status.HTTP_410_GONE,
    "upload_not_found": status.HTTP_404_NOT_FOUND,
    "upload_object_conflict": status.HTTP_409_CONFLICT,
    "source_hash_mismatch": status.HTTP_409_CONFLICT,
    "invalid_idempotency_key": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "processing_dispatch_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
}


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    request_id = request.state.request_id
    envelope = ErrorEnvelope(
        error=ErrorBody(
            code=code,
            message=message,
            request_id=request_id,
            details=details or {},
        )
    )
    return JSONResponse(
        status_code=status_code,
        headers={"X-Request-ID": request_id},
        content=envelope.model_dump(mode="json"),
    )


def create_app(
    services: BackendServices,
    *,
    sse_poll_interval: float = 0.5,
    max_upload_bytes: int = 20 * 1024 * 1024,
    cors_origins: Sequence[str] = (),
) -> FastAPI:
    app = FastAPI(
        title="StyleCapture Product API",
        version="0.1.0",
        description="Versioned capture and digital wardrobe capabilities.",
    )
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=[
                "Content-Type",
                "Idempotency-Key",
                "X-Request-ID",
                "X-StyleCapture-User",
            ],
            expose_headers=["X-Request-ID"],
        )

    @app.middleware("http")
    async def request_identity(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(CaptureError)
    async def capture_error_handler(request: Request, error: CaptureError) -> JSONResponse:
        return _error_response(
            request,
            status_code=CAPTURE_ERROR_STATUS.get(error.code, status.HTTP_400_BAD_REQUEST),
            code=error.code,
            message=error.message,
            details=error.details,
        )

    @app.exception_handler(JobNotFoundError)
    async def job_not_found_handler(request: Request, error: LookupError) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="job_not_found",
            message="The processing job does not exist",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="request_invalid",
            message="The request does not match the API contract",
            details={"violations": jsonable_encoder(error.errors())},
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(
        build_capture_router(
            CaptureHttpServices(
                capture=services.capture,
                jobs=services.jobs,
                objects=services.objects,
            ),
            sse_poll_interval=sse_poll_interval,
            max_upload_bytes=max_upload_bytes,
        )
    )
    return app
