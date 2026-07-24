from __future__ import annotations

from fastapi import FastAPI

from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.infrastructure.object_store import LocalObjectStore
from stylecapture_backend.features.capture.infrastructure.repository import (
    SqlAlchemyCaptureRepository,
)
from stylecapture_backend.features.capture.infrastructure.tasks import CeleryJobDispatcher
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.features.wardrobe.infrastructure.repository import (
    SqlAlchemyWardrobeRepository,
)
from stylecapture_backend.main import BackendServices, create_app
from stylecapture_backend.platform.celery import build_celery
from stylecapture_backend.platform.config import BackendSettings
from stylecapture_backend.platform.database import build_session_factory


def build_app() -> FastAPI:
    settings = BackendSettings()  # type: ignore[call-arg]
    database_url = settings.database_url.get_secret_value()
    redis_url = settings.redis_url.get_secret_value()
    sessions = build_session_factory(database_url)
    repository = SqlAlchemyCaptureRepository(sessions)
    wardrobe_repository = SqlAlchemyWardrobeRepository(sessions)
    objects = LocalObjectStore(
        root=settings.upload_root,
        signing_secret=settings.upload_signing_secret.get_secret_value(),
        public_upload_prefix=settings.public_upload_prefix,
        max_upload_bytes=settings.max_upload_bytes,
        max_image_pixels=settings.max_image_pixels,
    )
    dispatcher = CeleryJobDispatcher(
        build_celery(redis_url),
        queue=settings.capture_queue,
    )
    retries = JobRetryApplication(
        jobs=repository,
        dispatcher=dispatcher,
    )
    return create_app(
        BackendServices(
            capture=CaptureApplication(
                captures=repository,
                objects=objects,
                dispatcher=dispatcher,
            ),
            jobs=repository,
            objects=objects,
            retries=retries,
            wardrobe=WardrobeApplication(
                wardrobe=wardrobe_repository,
                sources=objects,
                jobs=repository,
                retries=retries,
            ),
        ),
        max_upload_bytes=settings.max_upload_bytes,
        cors_origins=settings.cors_origins,
        session_signing_secret=settings.session_signing_secret.get_secret_value(),
        session_cookie_secure=settings.session_cookie_secure,
    )
