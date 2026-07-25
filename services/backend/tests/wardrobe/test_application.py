from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    OwnershipState,
)
from stylecapture_backend.features.capture.processing import ImagePayload
from stylecapture_backend.features.wardrobe.application import (
    SourceDeletedNotRetryableError,
    WardrobeApplication,
    WardrobeNotFoundError,
)
from stylecapture_backend.features.wardrobe.domain import (
    FieldProvenance,
    ItemStatus,
    WardrobeItem,
)


class MemoryWardrobe:
    def __init__(self, items: list[WardrobeItem]) -> None:
        self.items = {item.id: item for item in items}

    async def list_for_user(self, user_id: UUID) -> list[WardrobeItem]:
        return [item for item in self.items.values() if item.user_id == user_id]

    async def get_for_user(self, item_id: UUID, user_id: UUID) -> WardrobeItem | None:
        item = self.items.get(item_id)
        return item if item is not None and item.user_id == user_id else None

    async def save(self, item: WardrobeItem) -> WardrobeItem:
        self.items[item.id] = item
        return item

    async def save_user_state(self, item: WardrobeItem) -> WardrobeItem:
        return await self.save(item)


class MemorySources:
    def __init__(self, image: ImagePayload) -> None:
        self.image = image
        self.deleted: list[str] = []

    def read_image(self, object_key: str) -> ImagePayload:
        if object_key in self.deleted:
            raise FileNotFoundError(object_key)
        return self.image

    def delete(self, object_key: str) -> None:
        self.deleted.append(object_key)


class FailingDeleteSources(MemorySources):
    def __init__(self, image: ImagePayload) -> None:
        super().__init__(image)
        self.fail_delete = True

    def delete(self, object_key: str) -> None:
        if self.fail_delete:
            raise OSError("object store temporarily unavailable")
        super().delete(object_key)


def make_item(*, user_id: UUID) -> WardrobeItem:
    capture = Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.CAMERA,
            object_key="originals/2026/07/25/item.jpg",
            sha256="a" * 64,
        ),
        ownership=OwnershipState.OWNED,
    )
    return WardrobeItem.processing(capture).with_status(ItemStatus.READY)


@pytest.mark.asyncio
async def test_lists_only_the_current_users_items_and_returns_source_kind() -> None:
    user_id = uuid4()
    own_item = make_item(user_id=user_id)
    repository = MemoryWardrobe([own_item, make_item(user_id=uuid4())])
    application = WardrobeApplication(
        wardrobe=repository,
        sources=MemorySources(
            ImagePayload(
                object_key=own_item.source_object_key,
                content_type="image/jpeg",
                body=b"image",
                sha256="a" * 64,
            )
        ),
    )

    items = await application.list_items(user_id)

    assert items == [own_item]
    assert items[0].source_kind is CaptureSourceKind.CAMERA


@pytest.mark.asyncio
async def test_lists_reviewed_showcase_items_before_later_user_captures() -> None:
    user_id = uuid4()
    uploaded = make_item(user_id=user_id)
    showcase_second = make_item(user_id=user_id).with_model_metadata(
        {"showcase_order": 1}
    )
    showcase_first = make_item(user_id=user_id).with_model_metadata(
        {"showcase_order": 0}
    )
    application = WardrobeApplication(
        wardrobe=MemoryWardrobe([uploaded, showcase_second, showcase_first]),
        sources=MemorySources(
            ImagePayload(
                object_key=uploaded.source_object_key,
                content_type="image/jpeg",
                body=b"image",
                sha256="a" * 64,
            )
        ),
    )

    items = await application.list_items(user_id)

    assert items == [showcase_first, showcase_second, uploaded]


@pytest.mark.asyncio
async def test_user_corrections_and_ownership_are_persisted_as_locked_truth() -> None:
    user_id = uuid4()
    item = make_item(user_id=user_id)
    repository = MemoryWardrobe([item])
    application = WardrobeApplication(
        wardrobe=repository,
        sources=MemorySources(
            ImagePayload(
                object_key=item.source_object_key,
                content_type="image/jpeg",
                body=b"image",
                sha256="a" * 64,
            )
        ),
    )

    updated = await application.update_item(
        user_id,
        item.id,
        corrections={"category": "outerwear", "colors": ["navy", "white"]},
        ownership=OwnershipState.INSPIRATION,
    )

    assert updated.ownership is OwnershipState.INSPIRATION
    assert updated.attributes.fields["category"].value == "outerwear"
    assert updated.attributes.fields["category"].provenance is FieldProvenance.USER
    assert updated.attributes.fields["category"].locked is True


@pytest.mark.asyncio
async def test_source_access_and_deletion_are_owner_scoped() -> None:
    user_id = uuid4()
    item = make_item(user_id=user_id)
    source = MemorySources(
        ImagePayload(
            object_key=item.source_object_key,
            content_type="image/jpeg",
            body=b"image",
            sha256="a" * 64,
        )
    )
    repository = MemoryWardrobe([item])
    application = WardrobeApplication(
        wardrobe=repository,
        sources=source,
    )

    image = await application.read_source(user_id, item.id)
    await application.delete_source(user_id, item.id)

    assert image.body == b"image"
    with pytest.raises(FileNotFoundError):
        await application.read_source(user_id, item.id)
    with pytest.raises(WardrobeNotFoundError):
        await application.read_source(uuid4(), item.id)
    assert repository.items[item.id].source_available is False


@pytest.mark.asyncio
async def test_failed_source_delete_remains_visible_for_safe_retry() -> None:
    user_id = uuid4()
    item = make_item(user_id=user_id)
    source = FailingDeleteSources(
        ImagePayload(
            object_key=item.source_object_key,
            content_type="image/jpeg",
            body=b"image",
            sha256="a" * 64,
        )
    )
    repository = MemoryWardrobe([item])
    application = WardrobeApplication(wardrobe=repository, sources=source)

    with pytest.raises(OSError):
        await application.delete_source(user_id, item.id)

    assert repository.items[item.id].source_available is True
    source.fail_delete = False
    await application.delete_source(user_id, item.id)
    assert repository.items[item.id].source_available is False


@pytest.mark.asyncio
async def test_deleted_source_cannot_be_retried() -> None:
    user_id = uuid4()
    item = make_item(user_id=user_id)
    repository = MemoryWardrobe([item])
    source = MemorySources(
        ImagePayload(
            object_key=item.source_object_key,
            content_type="image/jpeg",
            body=b"image",
            sha256="a" * 64,
        )
    )
    application = WardrobeApplication(
        wardrobe=repository,
        sources=source,
    )

    await application.delete_source(user_id, item.id)

    with pytest.raises(SourceDeletedNotRetryableError):
        await application.retry_item(user_id, item.id)
