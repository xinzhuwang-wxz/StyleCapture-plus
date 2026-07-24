import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    OwnershipState,
)
from stylecapture_backend.features.wardrobe.domain import (
    FieldProvenance,
    ItemStatus,
    ModelField,
    WardrobeItem,
)
from stylecapture_backend.features.wardrobe.infrastructure.repository import (
    SqlAlchemyWardrobeRepository,
)
from stylecapture_backend.platform.database import build_session_factory, run_migrations

TEST_DATABASE_URL = os.environ.get(
    "STYLECAPTURE_TEST_DATABASE_URL",
    "postgresql+asyncpg://stylecapture:stylecapture@127.0.0.1:5434/stylecapture",
)


@pytest.mark.asyncio
async def test_wardrobe_repository_round_trips_locked_fields_metadata_and_vector() -> None:
    await run_migrations(TEST_DATABASE_URL)
    sessions = build_session_factory(TEST_DATABASE_URL)
    async with sessions() as session:
        await session.execute(text("TRUNCATE TABLE items, processing_jobs, captures CASCADE"))
        capture = Capture.create(
            user_id=uuid4(),
            source=CaptureSource(
                kind=CaptureSourceKind.UPLOAD,
                object_key="originals/2026/07/25/wardrobe.png",
                sha256="f" * 64,
            ),
            ownership=OwnershipState.OWNED,
        )
        await session.execute(
            text(
                """
                INSERT INTO captures (
                    id, user_id, source_kind, object_key, sha256,
                    ownership, idempotency_key, created_at
                ) VALUES (
                    :id, :user_id, :source_kind, :object_key, :sha256,
                    :ownership, :idempotency_key, :created_at
                )
                """
            ),
            {
                "id": capture.id,
                "user_id": capture.user_id,
                "source_kind": capture.source.kind.value,
                "object_key": capture.source.object_key,
                "sha256": capture.source.sha256,
                "ownership": capture.ownership.value,
                "idempotency_key": "wardrobe-repo-001",
                "created_at": capture.created_at,
            },
        )
        await session.commit()

    repository = SqlAlchemyWardrobeRepository(sessions)
    item = WardrobeItem.processing(capture).correct("category", "outerwear")
    item = item.apply_model(
        {
            "category": ModelField("tops", 0.98, "vision-v1"),
            "description": ModelField("一件蓝色外套", 0.9, "vision-v1"),
        },
        {"capability_alias": "vision_understanding", "schema_version": "garment-v1"},
    )
    item = item.with_embedding(
        (1.0,) + (0.0,) * 767,
        model_version="Marqo/marqo-fashionSigLIP@c56244c",
    ).with_status(ItemStatus.READY)

    await repository.save(item)
    stored = await repository.get_by_capture(capture.id)

    assert stored is not None
    assert stored == item
    assert stored.attributes.fields["category"].value == "outerwear"
    assert stored.attributes.fields["category"].provenance is FieldProvenance.USER
    assert stored.attributes.fields["description"].value == "一件蓝色外套"
    assert str(stored.model_metadata["embedding_model"]).startswith("Marqo/")
    assert stored.embedding == (1.0,) + (0.0,) * 767
