from __future__ import annotations

from dataclasses import replace
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    OwnershipState,
)
from stylecapture_backend.features.capture.ports import (
    CaptureRepository,
    JobDispatcher,
    JobRepository,
    ObjectStore,
)
from stylecapture_backend.features.capture.processing import ImagePayload
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.features.wardrobe.domain import ItemStatus, WardrobeItem
from stylecapture_backend.main import BackendServices, create_app
from stylecapture_backend.platform.session import SESSION_COOKIE_NAME, SessionSigner

SESSION_SECRET = "wardrobe-http-session-secret-with-enough-entropy"


class MemoryWardrobe:
    def __init__(self, item: WardrobeItem) -> None:
        self.item = item

    async def list_for_user(self, user_id: UUID) -> list[WardrobeItem]:
        return [self.item] if self.item.user_id == user_id else []

    async def get_for_user(self, item_id: UUID, user_id: UUID) -> WardrobeItem | None:
        if self.item.id == item_id and self.item.user_id == user_id:
            return self.item
        return None

    async def save(self, item: WardrobeItem) -> WardrobeItem:
        self.item = item
        return item

    async def save_user_state(self, item: WardrobeItem) -> WardrobeItem:
        return await self.save(item)


class MemorySources:
    def __init__(self, item: WardrobeItem) -> None:
        self.item = item
        self.deleted = False

    def read_image(self, object_key: str) -> ImagePayload:
        if object_key == self.item.display_object_key:
            return ImagePayload(
                object_key=object_key,
                content_type="image/png",
                body=b"transparent-display-bytes",
                sha256="c" * 64,
            )
        if self.deleted:
            raise FileNotFoundError(object_key)
        return ImagePayload(
            object_key=self.item.source_object_key,
            content_type="image/jpeg",
            body=b"real-image-bytes",
            sha256="b" * 64,
        )

    def delete(self, object_key: str) -> None:
        self.deleted = True


def build_client() -> tuple[AsyncClient, UUID, WardrobeItem]:
    user_id = uuid4()
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.UPLOAD,
            object_key="originals/2026/07/25/http.jpg",
            sha256="b" * 64,
        ),
        ownership=OwnershipState.OWNED,
    )
    item = replace(
        WardrobeItem.processing(capture).with_status(ItemStatus.READY),
        display_object_key="derived/items/http-display.png",
        model_metadata={
            "capability_alias": "vision_understanding",
            "provider_model": "private-provider-endpoint",
            "prompt_version": "garment-v1",
            "embedding_model": "private-embedding-model",
        },
    )
    repository = MemoryWardrobe(item)
    sources = MemorySources(item)
    no_op = cast(object, object())
    app = create_app(
        BackendServices(
            capture=CaptureApplication(
                captures=cast(CaptureRepository, no_op),
                objects=cast(ObjectStore, no_op),
                dispatcher=cast(JobDispatcher, no_op),
            ),
            jobs=cast(JobRepository, no_op),
            objects=cast(ObjectStore, no_op),
            retries=cast(JobRetryApplication, no_op),
            wardrobe=WardrobeApplication(wardrobe=repository, sources=sources),
        ),
        session_signing_secret=SESSION_SECRET,
    )
    _, token = SessionSigner(SESSION_SECRET).issue(user_id)
    return (
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={SESSION_COOKIE_NAME: token},
        ),
        user_id,
        item,
    )


@pytest.mark.asyncio
async def test_lists_updates_and_serves_the_owner_scoped_real_item() -> None:
    client, _, item = build_client()

    async with client:
        listed = await client.get("/v1/items")
        updated = await client.patch(
            f"/v1/items/{item.id}",
            json={
                "ownership": "inspiration",
                "corrections": {"description": "我的蓝色短外套"},
            },
        )
        image = await client.get(f"/v1/items/{item.id}/image")
        source_image = await client.get(f"/v1/items/{item.id}/source")
        deleted = await client.delete(f"/v1/items/{item.id}/source")
        missing_image = await client.get(f"/v1/items/{item.id}/image")
        missing_source = await client.get(f"/v1/items/{item.id}/source")
        deleted_item = await client.get(f"/v1/items/{item.id}")
        rejected_retry = await client.post(f"/v1/items/{item.id}/retry")

    assert listed.status_code == 200
    assert listed.headers["cache-control"] == "private, no-store"
    assert listed.headers["vary"] == "Cookie"
    assert listed.json()["items"][0]["source_kind"] == "upload"
    assert listed.json()["items"][0]["source_available"] is True
    assert listed.json()["items"][0]["display_image_url"].endswith(f"/{item.id}/image")
    assert listed.json()["items"][0]["source_image_url"].endswith(f"/{item.id}/source")
    assert listed.json()["items"][0]["model_metadata"]["capability_alias"] == (
        "vision_understanding"
    )
    assert "provider_model" not in listed.json()["items"][0]["model_metadata"]
    assert "embedding_model" not in listed.json()["items"][0]["model_metadata"]
    assert updated.status_code == 200
    assert updated.json()["ownership"] == "inspiration"
    assert updated.json()["attributes"]["description"]["provenance"] == "user"
    assert image.status_code == 200
    assert image.content == b"transparent-display-bytes"
    assert image.headers["content-type"] == "image/png"
    assert image.headers["cache-control"] == "private, no-store"
    assert source_image.status_code == 200
    assert source_image.content == b"real-image-bytes"
    assert source_image.headers["content-type"] == "image/jpeg"
    assert deleted.status_code == 204
    assert missing_image.status_code == 200
    assert missing_image.content == b"transparent-display-bytes"
    assert missing_source.status_code == 404
    assert missing_source.json()["error"]["code"] == "item_source_not_found"
    assert deleted_item.json()["source_available"] is False
    assert rejected_retry.status_code == 409
    assert rejected_retry.json()["error"]["code"] == "source_deleted_not_retryable"


@pytest.mark.asyncio
async def test_item_routes_do_not_reveal_another_users_asset() -> None:
    client, _, item = build_client()
    _, token = SessionSigner(SESSION_SECRET).issue(uuid4())
    client.cookies.set(SESSION_COOKIE_NAME, token)

    async with client:
        response = await client.get(f"/v1/items/{item.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "item_not_found"
