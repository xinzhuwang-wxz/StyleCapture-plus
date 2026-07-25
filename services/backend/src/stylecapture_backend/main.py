from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Cookie, FastAPI, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware

from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    CaptureError,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.interfaces.http import (
    CaptureHttpServices,
    JobNotFoundError,
    build_capture_router,
)
from stylecapture_backend.features.capture.ports import JobRepository, ObjectStore
from stylecapture_backend.features.item_presentation.interfaces.http import (
    ItemPresentationHttpServices,
    build_item_presentation_router,
)
from stylecapture_backend.features.item_presentation.ports import (
    ItemPresentationDispatchError,
    ItemPresentationIdempotencyConflict,
    ItemPresentationNotFound,
)
from stylecapture_backend.features.look.application import LookNotFoundError
from stylecapture_backend.features.look.interfaces.http import (
    LookHttpServices,
    LookImageNotFoundError,
    build_look_router,
)
from stylecapture_backend.features.outfit.application import (
    OutfitPlanInvalidError,
    OutfitWardrobeEmptyError,
    OutfitWorkflowTraceNotFoundError,
)
from stylecapture_backend.features.outfit.infrastructure.tickets import (
    InvalidOutfitPlanTicket,
)
from stylecapture_backend.features.outfit.interfaces.http import (
    OutfitHttpServices,
    build_outfit_router,
)
from stylecapture_backend.features.pixel_trial.infrastructure.tasks import PixelTrialDispatchError
from stylecapture_backend.features.pixel_trial.interfaces.http import (
    PixelTrialHttpServices,
    build_pixel_trial_router,
)
from stylecapture_backend.features.pixel_trial.ports import (
    PixelTrialIdempotencyConflict,
    PixelTrialNotFound,
)
from stylecapture_backend.features.render.infrastructure.tasks import RenderDispatchError
from stylecapture_backend.features.render.interfaces.http import (
    RenderHttpServices,
    build_render_router,
)
from stylecapture_backend.features.render.ports import (
    RenderArtifactNotFound,
    RenderIdempotencyConflict,
)
from stylecapture_backend.features.wardrobe.application import (
    SourceDeletedNotRetryableError,
    WardrobeApplication,
    WardrobeNotFoundError,
    WardrobeValidationError,
)
from stylecapture_backend.features.wardrobe.demo import DemoWardrobeBootstrapper
from stylecapture_backend.features.wardrobe.interfaces.http import (
    ItemSourceNotFoundError,
    build_wardrobe_router,
)
from stylecapture_backend.platform.errors import ErrorBody, ErrorEnvelope
from stylecapture_backend.platform.session import (
    SESSION_COOKIE_NAME,
    InvalidSessionError,
    SessionSigner,
)


@dataclass(frozen=True, slots=True)
class BackendServices:
    capture: CaptureApplication
    jobs: JobRepository
    objects: ObjectStore
    retries: JobRetryApplication
    wardrobe: WardrobeApplication
    looks: LookHttpServices | None = None
    renders: RenderHttpServices | None = None
    outfits: OutfitHttpServices | None = None
    pixel_trials: PixelTrialHttpServices | None = None
    item_presentations: ItemPresentationHttpServices | None = None
    demo_wardrobe: DemoWardrobeBootstrapper | None = None


CAPTURE_ERROR_STATUS = {
    "unsupported_image_type": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    "upload_size_invalid": status.HTTP_413_CONTENT_TOO_LARGE,
    "upload_token_expired": status.HTTP_410_GONE,
    "upload_not_found": status.HTTP_404_NOT_FOUND,
    "upload_already_attached": status.HTTP_409_CONFLICT,
    "upload_unattached_quota_exceeded": status.HTTP_429_TOO_MANY_REQUESTS,
    "upload_daily_quota_exceeded": status.HTTP_429_TOO_MANY_REQUESTS,
    "upload_capacity_exceeded": status.HTTP_503_SERVICE_UNAVAILABLE,
    "upload_object_conflict": status.HTTP_409_CONFLICT,
    "source_hash_mismatch": status.HTTP_409_CONFLICT,
    "invalid_idempotency_key": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "feed_context_invalid": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "processing_dispatch_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
    "job_not_found": status.HTTP_404_NOT_FOUND,
    "job_not_retryable": status.HTTP_409_CONFLICT,
}

CurrentUser = Callable[..., UUID]
DEFAULT_DEMO_SEED_NEW_SESSION_QUOTA = 64


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


def _public_validation_errors(error: RequestValidationError) -> list[dict[str, object]]:
    encoded = jsonable_encoder(error.errors())
    if not isinstance(encoded, list):
        return []
    return [
        {key: value for key, value in violation.items() if key != "input"}
        for violation in encoded
        if isinstance(violation, dict)
    ]


def create_app(
    services: BackendServices,
    *,
    sse_poll_interval: float = 0.5,
    max_upload_bytes: int = 20 * 1024 * 1024,
    cors_origins: Sequence[str] = (),
    session_signing_secret: str = "test-session-signing-secret-with-enough-entropy",
    session_cookie_secure: bool = False,
    demo_seed_new_session_quota: int = DEFAULT_DEMO_SEED_NEW_SESSION_QUOTA,
) -> FastAPI:
    if demo_seed_new_session_quota < 0:
        raise ValueError("demo seed new-session quota must not be negative")
    sessions = SessionSigner(session_signing_secret)
    demo_seed_admission_lock = asyncio.Lock()
    admitted_demo_seed_sessions = 0

    async def should_seed_demo_wardrobe(*, existing_user: bool) -> bool:
        nonlocal admitted_demo_seed_sessions
        async with demo_seed_admission_lock:
            if existing_user:
                return True
            if admitted_demo_seed_sessions >= demo_seed_new_session_quota:
                return False
            admitted_demo_seed_sessions += 1
            return True

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
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Idempotency-Key", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
        )

    def current_user(
        session_token: Annotated[
            str | None,
            Cookie(alias=SESSION_COOKIE_NAME),
        ] = None,
    ) -> UUID:
        if session_token is None:
            raise InvalidSessionError("Session is required")
        return sessions.verify(session_token)

    @app.middleware("http")
    async def request_identity(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        if request.url.path.startswith("/v1/"):
            response.headers.setdefault("Cache-Control", "private, no-store")
            vary = {
                value.strip()
                for value in response.headers.get("Vary", "").split(",")
                if value.strip()
            }
            vary.add("Cookie")
            response.headers["Vary"] = ", ".join(sorted(vary))
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

    @app.exception_handler(InvalidSessionError)
    async def invalid_session_handler(
        request: Request,
        error: InvalidSessionError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="session_invalid",
            message=str(error),
        )

    @app.exception_handler(JobNotFoundError)
    async def job_not_found_handler(request: Request, error: LookupError) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="job_not_found",
            message="The processing job does not exist",
        )

    @app.exception_handler(WardrobeNotFoundError)
    async def wardrobe_not_found_handler(
        request: Request,
        error: LookupError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="item_not_found",
            message="The wardrobe item does not exist",
        )

    @app.exception_handler(ItemSourceNotFoundError)
    async def item_source_not_found_handler(
        request: Request,
        error: FileNotFoundError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="item_source_not_found",
            message="The original item image is no longer available",
        )

    @app.exception_handler(LookNotFoundError)
    async def look_not_found_handler(
        request: Request,
        error: LookupError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="look_not_found",
            message="The saved Look does not exist",
        )

    @app.exception_handler(LookImageNotFoundError)
    async def look_image_not_found_handler(
        request: Request,
        error: FileNotFoundError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="look_image_not_found",
            message="The saved Look image is no longer available",
        )

    @app.exception_handler(RenderArtifactNotFound)
    async def render_artifact_not_found_handler(
        request: Request,
        error: LookupError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="render_artifact_not_found",
            message="The render artifact does not exist",
        )

    @app.exception_handler(RenderIdempotencyConflict)
    async def render_idempotency_conflict_handler(
        request: Request,
        error: ValueError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="render_idempotency_conflict",
            message=str(error),
        )

    @app.exception_handler(RenderDispatchError)
    async def render_dispatch_error_handler(
        request: Request,
        error: RuntimeError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="render_dispatch_unavailable",
            message="Render request was saved but the worker queue is temporarily unavailable",
        )

    @app.exception_handler(PixelTrialNotFound)
    async def pixel_trial_not_found_handler(
        request: Request,
        error: LookupError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="pixel_trial_not_found",
            message="The pixel trial does not exist",
        )

    @app.exception_handler(PixelTrialIdempotencyConflict)
    async def pixel_trial_idempotency_conflict_handler(
        request: Request,
        error: ValueError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="pixel_trial_idempotency_conflict",
            message=str(error),
        )

    @app.exception_handler(PixelTrialDispatchError)
    async def pixel_trial_dispatch_error_handler(
        request: Request,
        error: RuntimeError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="pixel_trial_dispatch_unavailable",
            message="Pixel trial request was saved but the worker queue is temporarily unavailable",
        )

    @app.exception_handler(ItemPresentationNotFound)
    async def item_presentation_not_found_handler(
        request: Request,
        error: LookupError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="item_presentation_not_found",
            message="The item presentation asset does not exist",
        )

    @app.exception_handler(ItemPresentationIdempotencyConflict)
    async def item_presentation_idempotency_conflict_handler(
        request: Request,
        error: ValueError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="item_presentation_idempotency_conflict",
            message=str(error),
        )

    @app.exception_handler(ItemPresentationDispatchError)
    async def item_presentation_dispatch_error_handler(
        request: Request,
        error: RuntimeError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="item_presentation_dispatch_unavailable",
            message="Item presentation request was saved but the worker queue is temporarily unavailable",
        )

    @app.exception_handler(OutfitWardrobeEmptyError)
    async def outfit_wardrobe_empty_handler(
        request: Request,
        error: ValueError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="outfit_wardrobe_empty",
            message=str(error),
        )

    @app.exception_handler(OutfitPlanInvalidError)
    async def outfit_plan_invalid_handler(
        request: Request,
        error: ValueError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="outfit_plan_invalid",
            message=str(error),
        )

    @app.exception_handler(OutfitWorkflowTraceNotFoundError)
    async def outfit_workflow_trace_not_found_handler(
        request: Request,
        error: LookupError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="outfit_trace_not_found",
            message="The outfit workflow trace does not exist",
        )

    @app.exception_handler(InvalidOutfitPlanTicket)
    async def outfit_plan_ticket_invalid_handler(
        request: Request,
        error: ValueError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="outfit_plan_invalid",
            message=str(error),
        )

    @app.exception_handler(WardrobeValidationError)
    async def wardrobe_validation_handler(
        request: Request,
        error: WardrobeValidationError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="item_update_invalid",
            message=str(error),
        )

    @app.exception_handler(SourceDeletedNotRetryableError)
    async def source_deleted_retry_handler(
        request: Request,
        error: SourceDeletedNotRetryableError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="source_deleted_not_retryable",
            message=str(error),
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
            details={"violations": _public_validation_errors(error)},
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/session", status_code=status.HTTP_201_CREATED)
    async def create_session(
        response: Response,
        session_token: Annotated[
            str | None,
            Cookie(alias=SESSION_COOKIE_NAME),
        ] = None,
    ) -> dict[str, UUID]:
        existing_user = False
        try:
            user_id = sessions.verify(session_token) if session_token else None
            existing_user = user_id is not None
        except InvalidSessionError:
            user_id = None
        user_id, token = sessions.issue(user_id)
        if services.demo_wardrobe is not None and await should_seed_demo_wardrobe(
            existing_user=existing_user
        ):
            await services.demo_wardrobe.ensure_for_user(user_id)
        response.set_cookie(
            SESSION_COOKIE_NAME,
            token,
            httponly=True,
            secure=session_cookie_secure,
            samesite="strict",
            max_age=sessions.max_age_seconds,
            path="/",
        )
        response.headers["Cache-Control"] = "private, no-store"
        return {"user_id": user_id}

    app.include_router(
        build_capture_router(
            CaptureHttpServices(
                capture=services.capture,
                jobs=services.jobs,
                objects=services.objects,
                retries=services.retries,
            ),
            sse_poll_interval=sse_poll_interval,
            max_upload_bytes=max_upload_bytes,
            current_user=current_user,
        )
    )
    app.include_router(
        build_wardrobe_router(
            services.wardrobe,
            current_user=current_user,
            presentations=services.item_presentations,
        )
    )
    if services.looks is not None:
        app.include_router(
            build_look_router(
                services.looks,
                current_user=current_user,
            )
        )
    if services.renders is not None:
        app.include_router(
            build_render_router(
                services.renders,
                current_user=current_user,
            )
        )
    if services.pixel_trials is not None:
        app.include_router(
            build_pixel_trial_router(
                services.pixel_trials,
                current_user=current_user,
            )
        )
    if services.item_presentations is not None:
        app.include_router(
            build_item_presentation_router(
                services.item_presentations,
                current_user=current_user,
            )
        )
    if services.outfits is not None:
        app.include_router(
            build_outfit_router(
                services.outfits,
                current_user=current_user,
            )
        )
    return app
