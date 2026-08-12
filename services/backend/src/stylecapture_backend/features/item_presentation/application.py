from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationAsset,
    ItemPresentationKind,
    ItemPresentationStatus,
)
from stylecapture_backend.features.item_presentation.ports import (
    ItemPresentationNotFound,
    ItemPresentationRepository,
    WardrobeItemReader,
)
from stylecapture_backend.features.render.domain import (
    RenderInputSignature,
    RenderOutput,
    RenderProviderTrace,
)
from stylecapture_backend.features.wardrobe.domain import WardrobeItem

PIXEL_ITEM_SIGNATURE_VERSION = "item-pixel-v5"
PIXEL_ITEM_PROMPT_VERSION = "stylecapture-item-pixel-2026-08-09-clean-subject"
PIXEL_ITEM_CAPABILITY_ID = "item.pixel_presentation"
PIXEL_ITEM_SCHEMA_VERSION = "ornate-asymmetric-pixel-card-square-v4"
FLAT_LAY_ITEM_SIGNATURE_VERSION = "item-flat-lay-v3"
FLAT_LAY_ITEM_CAPABILITY_ID = "item.generated_flat_lay"
FLAT_LAY_ITEM_SCHEMA_VERSION = "seedream-pure-white-3x4-v2"


@dataclass(frozen=True, slots=True)
class ItemPresentationView:
    id: UUID
    user_id: UUID
    item_id: UUID
    kind: ItemPresentationKind
    status: ItemPresentationStatus
    object_key: str | None
    content_hash: str | None
    content_type: str | None
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime
    dispatch_required: bool = False


class ItemPresentationApplication:
    def __init__(
        self,
        *,
        assets: ItemPresentationRepository,
        wardrobe: WardrobeItemReader,
    ) -> None:
        self._assets = assets
        self._wardrobe = wardrobe

    async def ensure_pixel_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        request_key: str | None = None,
    ) -> ItemPresentationView:
        item = await self._wardrobe.get_item(user_id, item_id)
        signature = pixel_item_signature(item)
        existing = await self._assets.find_current(
            user_id=user_id,
            item_id=item_id,
            kind=ItemPresentationKind.PIXEL_ITEM,
            input_signature=signature,
        )
        if existing is not None:
            return _view(existing)
        asset = ItemPresentationAsset.queued(
            user_id=user_id,
            item_id=item_id,
            kind=ItemPresentationKind.PIXEL_ITEM,
            input_signature=signature,
            request_key=request_key or _request_key(item_id=item_id, signature=signature),
        )
        stored = await self._assets.ensure_requested(asset)
        return _view(stored, dispatch_required=stored.status is ItemPresentationStatus.QUEUED)

    async def ensure_flat_lay_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
        request_key: str | None = None,
    ) -> ItemPresentationView:
        item = await self._wardrobe.get_item(user_id, item_id)
        signature = flat_lay_item_signature(item)
        existing = await self._assets.find_current(
            user_id=user_id,
            item_id=item_id,
            kind=ItemPresentationKind.FLAT_LAY_ITEM,
            input_signature=signature,
        )
        if existing is not None:
            return _view(existing)
        asset = ItemPresentationAsset.queued(
            user_id=user_id,
            item_id=item_id,
            kind=ItemPresentationKind.FLAT_LAY_ITEM,
            input_signature=signature,
            request_key=request_key or _flat_lay_request_key(item_id=item_id, signature=signature),
        )
        stored = await self._assets.ensure_requested(asset)
        return _view(stored, dispatch_required=stored.status is ItemPresentationStatus.QUEUED)

    async def get(self, *, user_id: UUID, asset_id: UUID) -> ItemPresentationView:
        asset = await self._assets.get_for_user(user_id=user_id, asset_id=asset_id)
        if asset is None:
            raise ItemPresentationNotFound("Item presentation asset not found")
        return _view(asset)

    async def get_current_flat_lay_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
    ) -> ItemPresentationView | None:
        """Return the current generated Item hero without creating new work."""
        item = await self._wardrobe.get_item(user_id, item_id)
        existing = await self._assets.find_current(
            user_id=user_id,
            item_id=item_id,
            kind=ItemPresentationKind.FLAT_LAY_ITEM,
            input_signature=flat_lay_item_signature(item),
        )
        return _view(existing) if existing is not None else None

    async def retry_pixel_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
    ) -> ItemPresentationView:
        item = await self._wardrobe.get_item(user_id, item_id)
        signature = pixel_item_signature(item)
        existing = await self._assets.find_current(
            user_id=user_id,
            item_id=item_id,
            kind=ItemPresentationKind.PIXEL_ITEM,
            input_signature=signature,
        )
        if existing is None:
            return await self.ensure_pixel_item(user_id=user_id, item_id=item_id)
        retried = await self._assets.save(existing.retry())
        return _view(
            retried,
            dispatch_required=retried.status is ItemPresentationStatus.QUEUED,
        )

    async def retry_flat_lay_item(
        self,
        *,
        user_id: UUID,
        item_id: UUID,
    ) -> ItemPresentationView:
        item = await self._wardrobe.get_item(user_id, item_id)
        signature = flat_lay_item_signature(item)
        existing = await self._assets.find_current(
            user_id=user_id,
            item_id=item_id,
            kind=ItemPresentationKind.FLAT_LAY_ITEM,
            input_signature=signature,
        )
        if existing is None:
            return await self.ensure_flat_lay_item(user_id=user_id, item_id=item_id)
        retried = await self._assets.save(existing.retry())
        return _view(
            retried,
            dispatch_required=retried.status is ItemPresentationStatus.QUEUED,
        )

    async def mark_running(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        provider_trace: RenderProviderTrace | None = None,
    ) -> ItemPresentationView:
        asset = await self._require_asset(user_id=user_id, asset_id=asset_id)
        return _view(await self._assets.save(asset.mark_running(provider_trace)))

    async def mark_succeeded(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        output: RenderOutput,
        provider_trace: RenderProviderTrace,
    ) -> ItemPresentationView:
        asset = await self._require_asset(user_id=user_id, asset_id=asset_id)
        return _view(
            await self._assets.save(
                asset.mark_succeeded(output=output, provider_trace=provider_trace)
            )
        )

    async def mark_failed(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        code: str,
        message: str,
    ) -> ItemPresentationView:
        asset = await self._require_asset(user_id=user_id, asset_id=asset_id)
        return _view(await self._assets.save(asset.mark_failed(code=code, message=message)))

    async def _require_asset(self, *, user_id: UUID, asset_id: UUID) -> ItemPresentationAsset:
        asset = await self._assets.get_for_user(user_id=user_id, asset_id=asset_id)
        if asset is None:
            raise ItemPresentationNotFound("Item presentation asset not found")
        return asset


def pixel_item_signature(item: WardrobeItem) -> RenderInputSignature:
    relevant_attributes = {
        name: {
            "value": field.value,
            "provenance": field.provenance.value,
        }
        for name, field in sorted(item.attributes.fields.items())
        if name
        in {
            "category",
            "subcategory",
            "colors",
            "materials",
            "pattern",
            "silhouette",
            "details",
        }
    }
    payload = {
        "item_id": str(item.id),
        "display_object_key": item.display_object_key,
        "source_object_key": item.source_object_key,
        "updated_at": item.updated_at.isoformat(),
        "attributes": relevant_attributes,
        "prompt_version": PIXEL_ITEM_PROMPT_VERSION,
    }
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return RenderInputSignature(version=PIXEL_ITEM_SIGNATURE_VERSION, hash=digest)


def flat_lay_item_signature(item: WardrobeItem) -> RenderInputSignature:
    relevant_attributes = {
        name: {
            "value": field.value,
            "provenance": field.provenance.value,
        }
        for name, field in sorted(item.attributes.fields.items())
        if name
        in {
            "description",
            "category",
            "subcategory",
            "colors",
            "materials",
            "pattern",
            "silhouette",
            "details",
        }
    }
    payload = {
        "item_id": str(item.id),
        "source_object_key": item.source_object_key,
        "updated_at": item.updated_at.isoformat(),
        "attributes": relevant_attributes,
        "capability_id": FLAT_LAY_ITEM_CAPABILITY_ID,
        "schema_version": FLAT_LAY_ITEM_SCHEMA_VERSION,
    }
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return RenderInputSignature(version=FLAT_LAY_ITEM_SIGNATURE_VERSION, hash=digest)


def _request_key(*, item_id: UUID, signature: RenderInputSignature) -> str:
    return f"item-pixel:{item_id}:{signature.version}:{signature.hash[:24]}"


def _flat_lay_request_key(*, item_id: UUID, signature: RenderInputSignature) -> str:
    return f"item-flat-lay:{item_id}:{signature.version}:{signature.hash[:24]}"


def _view(
    asset: ItemPresentationAsset,
    *,
    dispatch_required: bool = False,
) -> ItemPresentationView:
    return ItemPresentationView(
        id=asset.id,
        user_id=asset.user_id,
        item_id=asset.item_id,
        kind=asset.kind,
        status=asset.status,
        object_key=asset.output.object_key if asset.output is not None else None,
        content_hash=asset.output.content_hash if asset.output is not None else None,
        content_type=asset.output.content_type if asset.output is not None else None,
        failure_code=asset.failure_code,
        failure_message=asset.failure_message,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
        dispatch_required=dispatch_required,
    )
