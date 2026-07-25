from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.capture.domain import (
    ImagePayload,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.wardrobe.domain import WardrobeItem

EDITABLE_FIELDS = frozenset(
    {
        "category",
        "subcategory",
        "description",
        "colors",
        "materials",
        "pattern",
        "silhouette",
        "fit",
        "styles",
        "seasons",
        "occasions",
        "length",
        "neckline",
        "sleeve_type",
        "details",
    }
)


class WardrobeRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[WardrobeItem]: ...

    async def get_for_user(self, item_id: UUID, user_id: UUID) -> WardrobeItem | None: ...

    async def save(self, item: WardrobeItem) -> WardrobeItem: ...

    async def save_user_state(self, item: WardrobeItem) -> WardrobeItem: ...


class SourceStore(Protocol):
    def read_image(self, object_key: str) -> ImagePayload: ...

    def delete(self, object_key: str) -> None: ...


class WardrobeJobLookup(Protocol):
    async def get_by_capture_for_user(
        self,
        capture_id: UUID,
        user_id: UUID,
    ) -> ProcessingJob | None: ...


class WardrobeJobRetry(Protocol):
    async def retry(self, user_id: UUID, job_id: UUID) -> ProcessingJob: ...


class WardrobeNotFoundError(LookupError):
    pass


class WardrobeValidationError(ValueError):
    pass


class SourceDeletedNotRetryableError(ValueError):
    pass


class WardrobeApplication:
    def __init__(
        self,
        *,
        wardrobe: WardrobeRepository,
        sources: SourceStore,
        jobs: WardrobeJobLookup | None = None,
        retries: WardrobeJobRetry | None = None,
    ) -> None:
        self._wardrobe = wardrobe
        self._sources = sources
        self._jobs = jobs
        self._retries = retries

    async def list_items(self, user_id: UUID) -> list[WardrobeItem]:
        return await self._wardrobe.list_for_user(user_id)

    async def get_item(self, user_id: UUID, item_id: UUID) -> WardrobeItem:
        item = await self._wardrobe.get_for_user(item_id, user_id)
        if item is None:
            raise WardrobeNotFoundError(item_id)
        return item

    async def update_item(
        self,
        user_id: UUID,
        item_id: UUID,
        *,
        corrections: Mapping[str, object],
        ownership: OwnershipState | None,
    ) -> WardrobeItem:
        unknown_fields = set(corrections) - EDITABLE_FIELDS
        if unknown_fields:
            raise WardrobeValidationError(
                f"Unsupported wardrobe fields: {', '.join(sorted(unknown_fields))}"
            )
        item = await self.get_item(user_id, item_id)
        for name, value in corrections.items():
            item = item.correct(name, value)
        if ownership is not None:
            item = item.with_ownership(ownership)
        return await self._wardrobe.save_user_state(item)

    async def read_source(self, user_id: UUID, item_id: UUID) -> ImagePayload:
        item = await self.get_item(user_id, item_id)
        if not item.source_available:
            raise FileNotFoundError(item.source_object_key)
        return self._sources.read_image(item.source_object_key)

    async def read_display(self, user_id: UUID, item_id: UUID) -> ImagePayload:
        item = await self.get_item(user_id, item_id)
        object_key = item.display_object_key or item.source_object_key
        if object_key == item.source_object_key and not item.source_available:
            raise FileNotFoundError(item.source_object_key)
        return self._sources.read_image(object_key)

    async def delete_source(self, user_id: UUID, item_id: UUID) -> None:
        item = await self.get_item(user_id, item_id)
        self._sources.delete(item.source_object_key)
        if item.source_available:
            await self._wardrobe.save_user_state(item.with_source_deleted())

    async def retry_item(self, user_id: UUID, item_id: UUID) -> ProcessingJob:
        item = await self.get_item(user_id, item_id)
        if not item.source_available:
            raise SourceDeletedNotRetryableError(
                "The original image was deleted; upload it again to retry recognition"
            )
        if self._jobs is None or self._retries is None:
            raise RuntimeError("wardrobe retry capability is not configured")
        job = await self._jobs.get_by_capture_for_user(item.capture_id, user_id)
        if job is None:
            raise WardrobeNotFoundError(item_id)
        return await self._retries.retry(user_id, job.id)
