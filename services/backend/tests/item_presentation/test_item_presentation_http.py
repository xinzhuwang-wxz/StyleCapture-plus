from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.domain import CaptureSourceKind, OwnershipState
from stylecapture_backend.features.capture.ports import JobRepository, ObjectStore
from stylecapture_backend.features.item_presentation.application import (
    ItemPresentationApplication,
)
from stylecapture_backend.features.item_presentation.domain import ItemPresentationAsset
from stylecapture_backend.features.item_presentation.interfaces.http import (
    ItemPresentationHttpServices,
)
from stylecapture_backend.features.item_presentation.ports import (
    ItemPresentationIdempotencyConflict,
)
from stylecapture_backend.features.render.domain import RenderInputSignature
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.features.wardrobe.domain import ItemAttributes, ItemStatus, WardrobeItem
from stylecapture_backend.main import BackendServices, create_app
from stylecapture_backend.platform.session import SESSION_COOKIE_NAME, SessionSigner

SESSION_SECRET = "test-item-presentation-session-secret"


class MemoryItemPresentationAssets:
    def __init__(self) -> None:
        self.assets: dict[UUID, ItemPresentationAsset] = {}
        self.by_request: dict[tuple[UUID, str], UUID] = {}

    async def ensure_requested(
        self,
        asset: ItemPresentationAsset,
    ) -> ItemPresentationAsset:
        key = (asset.user_id, asset.request_key)
        existing_id = self.by_request.get(key)
        if existing_id is not None:
            existing = self.assets[existing_id]
            if (
                existing.item_id != asset.item_id
                or existing.kind is not asset.kind
                or existing.input_signature != asset.input_signature
            ):
                raise ItemPresentationIdempotencyConflict(
                    "Item presentation idempotency key was reused with different input"
                )
            return existing
        self.assets[asset.id] = asset
        self.by_request[key] = asset.id
        return asset

    async def save(self, asset: ItemPresentationAsset) -> ItemPresentationAsset:
        self.assets[asset.id] = asset
        self.by_request[(asset.user_id, asset.request_key)] = asset.id
        return asset

    async def find_current(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        kind,
        input_signature: RenderInputSignature,
    ) -> ItemPresentationAsset | None:
        for asset in self.assets.values():
            if (
                asset.user_id == user_id
                and asset.item_id == item_id
                and asset.kind is kind
                and asset.input_signature == input_signature
            ):
                return asset
        return None

    async def get_for_user(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
    ) -> ItemPresentationAsset | None:
        asset = self.assets.get(asset_id)
        return asset if asset is not None and asset.user_id == user_id else None


class FakeWardrobe:
    def __init__(self, item: WardrobeItem) -> None:
        self.item = item

    async def get_item(self, user_id: UUID, item_id: UUID) -> WardrobeItem:
        assert user_id == self.item.user_id
        assert item_id == self.item.id
        return self.item

    async def list_items(self, user_id: UUID) -> list[WardrobeItem]:
        assert user_id == self.item.user_id
        return [self.item]


class RecordingItemPresentationDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID]] = []

    def enqueue_item_presentation(self, *, user_id: UUID, asset_id: UUID) -> None:
        self.calls.append((user_id, asset_id))


def wardrobe_item(*, user_id: UUID) -> WardrobeItem:
    now = datetime.now(UTC)
    return WardrobeItem(
        id=uuid4(),
        user_id=user_id,
        capture_id=uuid4(),
        selection_key="selection_1",
        source_object_key="originals/2026/07/26/source.png",
        display_object_key="derived/items/display/source.png",
        source_available=True,
        source_kind=CaptureSourceKind.UPLOAD,
        ownership=OwnershipState.OWNED,
        status=ItemStatus.READY,
        attributes=ItemAttributes(),
        model_metadata={},
        embedding=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_item_pixel_presentation_http_creates_queued_task() -> None:
    repository = MemoryItemPresentationAssets()
    dispatcher = RecordingItemPresentationDispatcher()
    user_id = uuid4()
    item = wardrobe_item(user_id=user_id)
    app = create_app(
        BackendServices(
            capture=cast(CaptureApplication, None),
            jobs=cast(JobRepository, None),
            objects=cast(ObjectStore, None),
            retries=cast(JobRetryApplication, None),
            wardrobe=cast(WardrobeApplication, FakeWardrobe(item)),
            item_presentations=ItemPresentationHttpServices(
                presentations=ItemPresentationApplication(
                    assets=repository,
                    wardrobe=cast(WardrobeApplication, FakeWardrobe(item)),
                ),
                objects=cast(ObjectStore, None),
                dispatcher=dispatcher,
            ),
        ),
        sse_poll_interval=0,
        session_signing_secret=SESSION_SECRET,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, token = SessionSigner(SESSION_SECRET).issue(user_id)
        client.cookies.set(SESSION_COOKIE_NAME, token)

        wardrobe = await client.get("/v1/items")
        assert wardrobe.status_code == 200
        listed = wardrobe.json()["items"][0]
        assert listed["display_image_url"] == f"/v1/items/{item.id}/image"
        assert listed["pixel_image_url"] is None
        assert listed["pixel_image_status"] == "queued"
        assert dispatcher.calls and dispatcher.calls[0][0] == user_id

        created = await client.post(
            f"/v1/items/{item.id}/presentations/pixel",
            headers={"Idempotency-Key": "item-pixel-contract"},
        )
        assert created.status_code == 202
        payload = created.json()
        assert payload["item_id"] == str(item.id)
        assert payload["kind"] == "pixel_item"
        assert payload["status"] == "queued"
        assert payload["output_image_url"] is None
        assert "provider" not in payload
        assert "model" not in payload
        assert dispatcher.calls == [(user_id, UUID(payload["id"]))]

        not_ready = await client.get(f"/v1/item-presentations/{payload['id']}/image")
        assert not_ready.status_code == 404
        assert not_ready.json()["error"]["code"] == "item_presentation_not_found"
