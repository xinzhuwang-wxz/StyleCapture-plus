from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from stylecapture_backend.features.account.domain import SubjectDeletedError
from stylecapture_backend.features.account.infrastructure.repository import (
    InMemoryAccountRepository,
)
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    OwnershipState,
)
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationAsset,
    ItemPresentationKind,
)
from stylecapture_backend.features.item_presentation.infrastructure.repository import (
    SqlAlchemyItemPresentationRepository,
)
from stylecapture_backend.features.look.domain import (
    Look,
    LookAnalysis,
    LookAnalysisField,
    LookAnalysisMetadata,
)
from stylecapture_backend.features.look.infrastructure.repository import (
    SqlAlchemyLookRepository,
)
from stylecapture_backend.features.outfit.domain import (
    OutfitWorkflowStatus,
    OutfitWorkflowTrace,
    PurchaseDemandStatus,
)
from stylecapture_backend.features.outfit.infrastructure.repository import (
    SqlAlchemyOutfitWorkflowTraceRepository,
    SqlAlchemyPurchaseDemandRepository,
)
from stylecapture_backend.features.pixel_trial.domain import PixelTrial
from stylecapture_backend.features.pixel_trial.infrastructure.repository import (
    SqlAlchemyPixelTrialRepository,
)
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderInputSignature,
)
from stylecapture_backend.features.render.infrastructure.repository import (
    SqlAlchemyRenderArtifactRepository,
)
from stylecapture_backend.features.wardrobe.domain import WardrobeItem
from stylecapture_backend.features.wardrobe.infrastructure.repository import (
    SqlAlchemyWardrobeRepository,
)
from stylecapture_backend.platform.database import build_session_factory

TEST_DATABASE_URL = "postgresql+asyncpg://unused:unused@127.0.0.1:1/unused"


async def _deleted_accounts(user_id):
    accounts = InMemoryAccountRepository()
    await accounts.tombstone_subject(user_id, reason="account_deletion")
    return accounts


def _analysis() -> LookAnalysis:
    field = LookAnalysisField(value="minimal", confidence=0.9)
    return LookAnalysis(
        color=field,
        silhouette=field,
        material=field,
        layering=field,
        focal_point=field,
        scene=field,
        style=field,
        metadata=LookAnalysisMetadata(
            capability_alias="reasoning",
            model_version="test-v1",
            prompt_version="test-v1",
            schema_version="test-v1",
            taxonomy_version="test-v1",
            latency_ms=1,
        ),
    )


@pytest.mark.asyncio
async def test_all_account_owned_repositories_reject_writes_after_tombstone() -> None:
    user_id = uuid4()
    accounts = await _deleted_accounts(user_id)
    sessions = build_session_factory(TEST_DATABASE_URL)
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.UPLOAD,
            object_key="originals/deleted.png",
            sha256="a" * 64,
        ),
        ownership=OwnershipState.OWNED,
    )
    signature = RenderInputSignature(version="test-v1", hash="b" * 64)
    wardrobe = SqlAlchemyWardrobeRepository(sessions, subject_writes=accounts)
    looks = SqlAlchemyLookRepository(sessions, subject_writes=accounts)
    renders = SqlAlchemyRenderArtifactRepository(sessions, subject_writes=accounts)
    trials = SqlAlchemyPixelTrialRepository(sessions, subject_writes=accounts)
    presentations = SqlAlchemyItemPresentationRepository(sessions, subject_writes=accounts)
    traces = SqlAlchemyOutfitWorkflowTraceRepository(sessions, subject_writes=accounts)
    purchases = SqlAlchemyPurchaseDemandRepository(sessions, subject_writes=accounts)

    operations = (
        wardrobe.save(WardrobeItem.processing(capture)),
        looks.save(
            Look.ai_generated(
                user_id=user_id,
                source_selection_key="journey",
                analysis=_analysis(),
            )
        ),
        renders.ensure_requested(
            RenderArtifact.queued(
                user_id=user_id,
                look_id=uuid4(),
                kind=RenderArtifactKind.COLLAGE,
                input_signature=signature,
                request_key="deleted-render",
            )
        ),
        trials.ensure_requested(
            PixelTrial.queued(
                user_id=user_id,
                subject_object_key="originals/deleted-subject.png",
                request_key="deleted-trial",
            )
        ),
        presentations.ensure_requested(
            ItemPresentationAsset.queued(
                user_id=user_id,
                item_id=uuid4(),
                kind=ItemPresentationKind.PIXEL_ITEM,
                input_signature=signature,
                request_key="deleted-presentation",
            )
        ),
        traces.save(
            OutfitWorkflowTrace(
                id=uuid4(),
                user_id=user_id,
                request_id=uuid4(),
                status=OutfitWorkflowStatus.CANDIDATES_READY,
                explanation_state="rule_ranked",
                plan_count=1,
                capability_alias="deterministic_rules",
                model_version="test-v1",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ),
        purchases.advance(
            user_id=user_id,
            demand_id=uuid4(),
            target=PurchaseDemandStatus.PURCHASED_PENDING,
        ),
    )
    for operation in operations:
        with pytest.raises(SubjectDeletedError):
            await operation
