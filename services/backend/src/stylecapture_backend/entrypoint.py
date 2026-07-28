from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stylecapture_backend.features.account.application import AccountApplication
from stylecapture_backend.features.account.infrastructure.apple_identity import (
    AppleClientSecretSigner,
    AppleJWKSProvider,
    HttpAppleAuthorizationCodeExchange,
    HttpAppleProviderGrantRevoker,
    PyJWTAppleIdentityVerifier,
)
from stylecapture_backend.features.account.infrastructure.repository import (
    AppleProviderGrantCipher,
    SqlAlchemyAccountRepository,
    SqlAlchemyAppleProviderGrantRepository,
)
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.infrastructure.object_store import (
    LocalObjectStore,
    OwnerScopedUploadAcceptor,
)
from stylecapture_backend.features.capture.infrastructure.repository import (
    SqlAlchemyCaptureRepository,
)
from stylecapture_backend.features.capture.infrastructure.tasks import CeleryJobDispatcher
from stylecapture_backend.features.item_presentation.application import (
    ItemPresentationApplication,
)
from stylecapture_backend.features.item_presentation.infrastructure.repository import (
    SqlAlchemyItemPresentationRepository,
)
from stylecapture_backend.features.item_presentation.infrastructure.tasks import (
    CeleryItemPresentationDispatcher,
)
from stylecapture_backend.features.item_presentation.interfaces.http import (
    ItemPresentationHttpServices,
)
from stylecapture_backend.features.look.application import LookApplication
from stylecapture_backend.features.look.infrastructure.repository import (
    SqlAlchemyLookRepository,
)
from stylecapture_backend.features.look.interfaces.http import LookHttpServices
from stylecapture_backend.features.outfit.application import OutfitApplication
from stylecapture_backend.features.outfit.infrastructure.presentation import (
    DefaultOutfitPresentationScheduler,
)
from stylecapture_backend.features.outfit.infrastructure.repository import (
    SqlAlchemyOutfitWorkflowTraceRepository,
    SqlAlchemyPurchaseDemandRepository,
)
from stylecapture_backend.features.outfit.infrastructure.reranker import (
    LiteLLMOutfitReranker,
)
from stylecapture_backend.features.outfit.infrastructure.tickets import (
    OutfitPlanTicketSigner,
)
from stylecapture_backend.features.outfit.interfaces.http import OutfitHttpServices
from stylecapture_backend.features.pixel_trial.application import PixelTrialApplication
from stylecapture_backend.features.pixel_trial.infrastructure.repository import (
    SqlAlchemyPixelTrialRepository,
)
from stylecapture_backend.features.pixel_trial.infrastructure.tasks import (
    CeleryPixelTrialDispatcher,
)
from stylecapture_backend.features.pixel_trial.interfaces.http import PixelTrialHttpServices
from stylecapture_backend.features.render.application import RenderApplication
from stylecapture_backend.features.render.infrastructure.repository import (
    SqlAlchemyRenderArtifactRepository,
)
from stylecapture_backend.features.render.infrastructure.tasks import CeleryRenderDispatcher
from stylecapture_backend.features.render.interfaces.http import RenderHttpServices
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.features.wardrobe.infrastructure.curated_demo import (
    CuratedDemoWardrobeBootstrapper,
)
from stylecapture_backend.features.wardrobe.infrastructure.repository import (
    SqlAlchemyWardrobeRepository,
)
from stylecapture_backend.main import BackendServices, create_app
from stylecapture_backend.platform.celery import build_celery
from stylecapture_backend.platform.config import BackendSettings
from stylecapture_backend.platform.cost_guard import CostGuardLimits, RedisCostGuard
from stylecapture_backend.platform.database import build_session_factory


async def _readiness_check(
    *,
    database_sessions: async_sessionmaker[AsyncSession],
    redis_url: str,
    litellm_base_url: str,
) -> Mapping[str, bool]:
    checks: dict[str, bool] = {"database": False, "redis": False, "litellm": False}
    try:
        async with database_sessions() as session:
            await session.execute(text("select 1"))
        checks["database"] = True
    except SQLAlchemyError:
        checks["database"] = False
    try:
        redis = Redis.from_url(redis_url, decode_responses=True)
        try:
            checks["redis"] = bool(await redis.ping())
        finally:
            await redis.aclose()
    except RedisError:
        checks["redis"] = False
    liveliness_base_url = litellm_base_url.rsplit("/v1", 1)[0]
    try:
        async with httpx.AsyncClient(base_url=liveliness_base_url, timeout=2.0) as client:
            response = await client.get("/health/liveliness")
        checks["litellm"] = response.status_code < 500
    except httpx.HTTPError:
        checks["litellm"] = False
    return checks


def build_app() -> FastAPI:
    settings = BackendSettings()  # type: ignore[call-arg]
    database_url = settings.database_url.get_secret_value()
    redis_url = settings.redis_url.get_secret_value()
    sessions = build_session_factory(database_url)
    apple_provider_grant_cipher = AppleProviderGrantCipher(
        settings.apple_provider_grant_encryption_key.get_secret_value()
    )
    account_repository = SqlAlchemyAccountRepository(
        sessions,
        apple_provider_grant_cipher=apple_provider_grant_cipher,
    )
    apple_provider_grants = SqlAlchemyAppleProviderGrantRepository(
        sessions,
        cipher=apple_provider_grant_cipher,
    )
    repository = SqlAlchemyCaptureRepository(sessions, subject_writes=account_repository)
    apple_authorization_codes = None
    apple_provider_revoker = None
    if (
        settings.apple_team_id is not None
        and settings.apple_key_id is not None
        and settings.apple_private_key_pem.get_secret_value()
    ):
        apple_client_id = settings.apple_client_ids[0]
        apple_client_secret = AppleClientSecretSigner(
            team_id=settings.apple_team_id,
            key_id=settings.apple_key_id,
            client_id=apple_client_id,
            private_key_pem=settings.apple_private_key_pem.get_secret_value(),
        )
        apple_authorization_codes = HttpAppleAuthorizationCodeExchange(
            client_id=apple_client_id,
            client_secret=apple_client_secret,
        )
        apple_provider_revoker = HttpAppleProviderGrantRevoker(
            client_id=apple_client_id,
            client_secret=apple_client_secret,
        )
    wardrobe_repository = SqlAlchemyWardrobeRepository(
        sessions,
        subject_writes=account_repository,
    )
    look_repository = SqlAlchemyLookRepository(sessions, subject_writes=account_repository)
    render_repository = SqlAlchemyRenderArtifactRepository(
        sessions,
        subject_writes=account_repository,
    )
    pixel_trial_repository = SqlAlchemyPixelTrialRepository(
        sessions,
        subject_writes=account_repository,
    )
    item_presentation_repository = SqlAlchemyItemPresentationRepository(
        sessions,
        subject_writes=account_repository,
    )
    purchase_repository = SqlAlchemyPurchaseDemandRepository(
        sessions,
        wardrobe=wardrobe_repository,
        subject_writes=account_repository,
    )
    outfit_trace_repository = SqlAlchemyOutfitWorkflowTraceRepository(
        sessions,
        subject_writes=account_repository,
    )
    looks = LookApplication(looks=look_repository)
    renders = RenderApplication(artifacts=render_repository)
    pixel_trials = PixelTrialApplication(trials=pixel_trial_repository)
    objects = LocalObjectStore(
        root=settings.upload_root,
        signing_secret=settings.upload_signing_secret.get_secret_value(),
        public_upload_prefix=settings.public_upload_prefix,
        max_upload_bytes=settings.max_upload_bytes,
        max_image_pixels=settings.max_image_pixels,
    )
    uploads = OwnerScopedUploadAcceptor(
        objects=objects,
        subject_writes=account_repository,
    )
    demo_wardrobe = (
        CuratedDemoWardrobeBootstrapper(
            captures=repository,
            wardrobe=wardrobe_repository,
            looks=look_repository,
            objects=objects,
            assets_root=Path(__file__).resolve().parent / "demo_assets",
            item_presentations=item_presentation_repository,
            renders=render_repository,
        )
        if settings.demo_seed_enabled
        else None
    )
    dispatcher = CeleryJobDispatcher(
        build_celery(redis_url),
        queue=settings.capture_queue,
    )
    render_dispatcher = CeleryRenderDispatcher(
        build_celery(redis_url),
        queue=settings.render_queue,
    )
    pixel_trial_dispatcher = CeleryPixelTrialDispatcher(
        build_celery(redis_url),
        queue=settings.render_queue,
    )
    item_presentation_dispatcher = CeleryItemPresentationDispatcher(
        build_celery(redis_url),
        queue=settings.render_queue,
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
                whole_outfits=looks,
                subject_resolver=account_repository,
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
            looks=LookHttpServices(
                looks=looks,
                captures=repository,
                jobs=repository,
                objects=objects,
                retries=retries,
            ),
            renders=RenderHttpServices(
                renders=renders,
                looks=looks,
                captures=repository,
                objects=objects,
                dispatcher=render_dispatcher,
                subjects=account_repository,
            ),
            pixel_trials=PixelTrialHttpServices(
                trials=pixel_trials,
                objects=objects,
                dispatcher=pixel_trial_dispatcher,
                subjects=account_repository,
            ),
            item_presentations=ItemPresentationHttpServices(
                presentations=ItemPresentationApplication(
                    assets=item_presentation_repository,
                    wardrobe=WardrobeApplication(
                        wardrobe=wardrobe_repository,
                        sources=objects,
                        jobs=repository,
                        retries=retries,
                    ),
                ),
                objects=objects,
                dispatcher=item_presentation_dispatcher,
            ),
            outfits=OutfitHttpServices(
                outfits=OutfitApplication(
                    wardrobe=wardrobe_repository,
                    looks=look_repository,
                    reranker=LiteLLMOutfitReranker(
                        capability_alias=settings.reasoning_model_alias,
                        gateway_base_url=settings.litellm_base_url,
                        gateway_api_key=settings.litellm_api_key.get_secret_value(),
                        timeout_seconds=settings.outfit_reasoning_timeout_seconds,
                    ),
                    presentation=DefaultOutfitPresentationScheduler(
                        looks=looks,
                        captures=repository,
                        objects=objects,
                        renders=renders,
                        dispatcher=render_dispatcher,
                        subjects=account_repository,
                    ),
                    purchases=purchase_repository,
                    traces=outfit_trace_repository,
                ),
                tickets=OutfitPlanTicketSigner(settings.session_signing_secret.get_secret_value()),
            ),
            demo_wardrobe=demo_wardrobe,
            accounts=AccountApplication(
                repository=account_repository,
                apple_identity=PyJWTAppleIdentityVerifier(
                    jwks=AppleJWKSProvider(),
                    authorization_codes=apple_authorization_codes,
                    allowed_audiences=frozenset(settings.apple_client_ids),
                ),
                allowed_audiences=frozenset(settings.apple_client_ids),
                token_secret=settings.session_signing_secret.get_secret_value(),
                apple_provider_grants=apple_provider_grants,
                apple_provider_revoker=apple_provider_revoker,
            ),
            uploads=uploads,
        ),
        max_upload_bytes=settings.max_upload_bytes,
        cors_origins=settings.cors_origins,
        session_signing_secret=settings.session_signing_secret.get_secret_value(),
        session_cookie_secure=settings.session_cookie_secure,
        demo_seed_new_session_quota=settings.demo_seed_new_session_quota,
        readiness_check=lambda: _readiness_check(
            database_sessions=sessions,
            redis_url=redis_url,
            litellm_base_url=settings.litellm_base_url,
        ),
        cost_guard=RedisCostGuard(
            redis_url,
            limits=CostGuardLimits(
                window_seconds=settings.ai_cost_window_seconds,
                per_actor_requests=settings.ai_cost_actor_requests,
                per_client_requests=settings.ai_cost_client_requests,
                global_requests=settings.ai_cost_global_requests,
                per_actor_concurrency=settings.ai_cost_actor_concurrency,
                per_client_concurrency=settings.ai_cost_client_concurrency,
                global_concurrency=settings.ai_cost_global_concurrency,
            ),
        ),
    )
