from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from pillow_heif import from_pillow
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
from stylecapture_backend.features.wardrobe.interfaces.http import ItemResponse
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

    async def delete_for_user(self, item_id: UUID, user_id: UUID) -> bool:
        if self.item.id != item_id or self.item.user_id != user_id:
            return False
        self.item = replace(self.item, user_id=uuid4())
        return True


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


def build_client(
    *,
    status: ItemStatus = ItemStatus.READY,
) -> tuple[AsyncClient, UUID, WardrobeItem]:
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
        WardrobeItem.processing(capture).with_status(status),
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
    assert listed.json()["items"][0]["display_image_kind"] == "derived_garment"
    assert listed.json()["items"][0]["display_image_issue"] is None
    assert listed.json()["items"][0]["purchase_search_query"] == "同款穿搭单品"
    assert listed.json()["items"][0]["purchase_search_url"].startswith(
        "https://www.douyin.com/search/"
    )
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


def test_item_response_explains_why_an_ambiguous_upload_keeps_its_source_image() -> None:
    _, _, item = build_client()
    ambiguous = replace(
        item,
        display_object_key=None,
        model_metadata={
            "normalization": {
                "status": "not_applied",
                "reason": "multiple_garments",
                "candidate_count": 2,
            }
        },
    )

    response = ItemResponse.from_domain(ambiguous)

    assert response.display_image_kind == "source_capture"
    assert response.display_image_issue == "multiple_garments"


@pytest.mark.asyncio
async def test_item_routes_do_not_reveal_another_users_asset() -> None:
    client, _, item = build_client()
    _, token = SessionSigner(SESSION_SECRET).issue(uuid4())
    client.cookies.set(SESSION_COOKIE_NAME, token)

    async with client:
        response = await client.get(f"/v1/items/{item.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "item_not_found"


@pytest.mark.asyncio
async def test_owner_deletes_item_and_it_disappears_from_the_wardrobe() -> None:
    client, _, item = build_client()

    async with client:
        deleted = await client.delete(f"/v1/items/{item.id}")
        missing = await client.get(f"/v1/items/{item.id}")
        listed = await client.get("/v1/items")

    assert deleted.status_code == 204
    assert missing.status_code == 404
    assert listed.json()["items"] == []


@pytest.mark.asyncio
async def test_processing_item_cannot_be_deleted_and_resurrected_by_a_worker() -> None:
    client, _, item = build_client(status=ItemStatus.PROCESSING)

    async with client:
        deleted = await client.delete(f"/v1/items/{item.id}")
        still_present = await client.get(f"/v1/items/{item.id}")

    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "item_deletion_in_progress"
    assert still_present.status_code == 200


@pytest.mark.asyncio
async def test_heic_source_is_preserved_while_display_is_browser_safe() -> None:
    client, user_id, item = build_client()
    del client
    heic_buffer = BytesIO()
    from_pillow(Image.new("RGB", (20, 30), (120, 180, 140))).save(
        heic_buffer,
        format="HEIF",
    )
    heic_body = heic_buffer.getvalue()
    source_only = replace(
        item,
        display_object_key=None,
        source_object_key="originals/upload/phone-photo.heic",
    )

    class HeicSources:
        def read_image(self, object_key: str) -> ImagePayload:
            return ImagePayload(
                object_key=object_key,
                content_type="image/heic",
                body=heic_body,
                sha256="a" * 64,
            )

        def delete(self, object_key: str) -> None:
            raise AssertionError(f"unexpected delete: {object_key}")

    application = WardrobeApplication(
        wardrobe=MemoryWardrobe(source_only),
        sources=HeicSources(),
    )

    display = await application.read_display(user_id, source_only.id)
    source = await application.read_source(user_id, source_only.id)

    assert display.content_type == "image/jpeg"
    assert display.body.startswith(b"\xff\xd8\xff")
    assert source.content_type == "image/heic"
    assert source.body == heic_body
