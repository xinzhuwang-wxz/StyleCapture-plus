from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID

from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    ImagePayload,
    JobState,
    NormalizedPoint,
    OwnershipState,
    ProcessingJob,
)
from stylecapture_backend.features.capture.ports import CaptureRepository
from stylecapture_backend.features.item_presentation.application import (
    pixel_item_signature,
)
from stylecapture_backend.features.item_presentation.domain import (
    ItemPresentationAsset,
    ItemPresentationKind,
)
from stylecapture_backend.features.look.domain import (
    Look,
    LookAnalysis,
    LookAnalysisField,
    LookAnalysisMetadata,
    LookComponent,
    LookDeletionResult,
    LookSource,
    LookStatus,
)
from stylecapture_backend.features.render.domain import (
    RenderArtifact,
    RenderArtifactKind,
    RenderInputSignature,
    RenderOutput,
    RenderPrivacy,
    RenderProviderTrace,
)
from stylecapture_backend.features.wardrobe.domain import (
    FieldEnvelope,
    FieldProvenance,
    ItemAttributes,
    ItemStatus,
    WardrobeItem,
)


class DemoWardrobeRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[WardrobeItem]: ...

    async def get_by_capture(
        self,
        capture_id: UUID,
        selection_key: str = "whole_capture",
    ) -> WardrobeItem | None: ...

    async def save(self, item: WardrobeItem) -> WardrobeItem: ...

    async def delete_for_user(self, item_id: UUID, user_id: UUID) -> bool: ...


class DemoLookRepository(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[Look]: ...

    async def get_by_capture(
        self,
        capture_id: UUID,
        source_selection_key: str,
    ) -> Look | None: ...

    async def save(self, look: Look) -> Look: ...

    async def save_component(self, component: LookComponent) -> LookComponent: ...

    async def delete_for_user(
        self,
        look_id: UUID,
        user_id: UUID,
        *,
        delete_items: bool,
    ) -> LookDeletionResult | None: ...


class DemoObjectWriter(Protocol):
    def write_private_source_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload: ...

    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload: ...


class DemoItemPresentationRepository(Protocol):
    async def ensure_requested(
        self,
        asset: ItemPresentationAsset,
    ) -> ItemPresentationAsset: ...

    async def save(self, asset: ItemPresentationAsset) -> ItemPresentationAsset: ...


class DemoRenderArtifactRepository(Protocol):
    async def ensure_requested(self, artifact: RenderArtifact) -> RenderArtifact: ...

    async def save(self, artifact: RenderArtifact) -> RenderArtifact: ...


@dataclass(frozen=True, slots=True)
class SeedItem:
    key: str
    file_name: str
    name: str
    category: str
    subcategory: str
    ownership: OwnershipState
    colors: tuple[str, ...]
    styles: tuple[str, ...]
    source_ref: str
    pixel_file_name: str | None = None
    materials: tuple[str, ...] = ()
    pattern: str | None = None
    silhouette: str | None = None
    fit: str | None = None
    seasons: tuple[str, ...] = ()
    occasions: tuple[str, ...] = ()
    details: tuple[str, ...] = ()
    source_file_name: str | None = None
    source_pixel_file_name: str | None = None


@dataclass(frozen=True, slots=True)
class SeedLook:
    key: str
    file_name: str
    title: str
    item_keys: tuple[str, ...]
    scene: str
    style: str
    layering: str
    pixel_file_name: str | None = None


def _load_seed_manifest(path: Path) -> tuple[tuple[SeedItem, ...], tuple[SeedLook, ...]]:
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    if payload.get("schema_version") != "stylecapture-demo-seed-v1":
        raise ValueError("unsupported curated demo seed manifest")
    if payload.get("provenance") != "curated_seed":
        raise ValueError("curated demo seed manifest must declare curated_seed provenance")
    raw_items = cast(list[dict[str, object]], payload.get("items"))
    raw_looks = cast(list[dict[str, object]], payload.get("looks"))
    items = tuple(
        SeedItem(
            key=str(entry["seed_key"]),
            file_name=str(entry["product_image"]),
            pixel_file_name=str(entry["pixel_asset"]),
            name=str(entry["name"]),
            category=str(entry["category"]),
            subcategory=str(entry["subcategory"]),
            ownership=OwnershipState(str(entry["ownership"])),
            colors=tuple(str(value) for value in cast(list[object], entry["colors"])),
            styles=tuple(str(value) for value in cast(list[object], entry["styles"])),
            source_ref=str(entry["source_ref"]),
            materials=_optional_tuple(entry, "materials"),
            pattern=_optional_str(entry, "pattern"),
            silhouette=_optional_str(entry, "silhouette"),
            fit=_optional_str(entry, "fit"),
            seasons=_optional_tuple(entry, "seasons"),
            occasions=_optional_tuple(entry, "occasions"),
            details=_optional_tuple(entry, "details"),
            source_file_name=_nested_optional_str(entry, "source_files", "real"),
            source_pixel_file_name=_nested_optional_str(entry, "source_files", "pixel"),
        )
        for entry in raw_items
    )
    looks = tuple(
        SeedLook(
            key=str(entry["seed_key"]),
            file_name=str(entry["product_image"]),
            pixel_file_name=str(entry["pixel_asset"]),
            title=str(entry["title"]),
            item_keys=tuple(str(value) for value in cast(list[object], entry["item_keys"])),
            scene=str(entry["scene"]),
            style=str(entry["style"]),
            layering=str(entry["layering"]),
        )
        for entry in raw_looks
    )
    return items, looks


def _optional_tuple(entry: dict[str, object], key: str) -> tuple[str, ...]:
    values = entry.get(key)
    if values is None:
        return ()
    return tuple(str(value) for value in cast(list[object], values))


def _optional_str(entry: dict[str, object], key: str) -> str | None:
    value = entry.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _nested_optional_str(entry: dict[str, object], key: str, nested_key: str) -> str | None:
    value = entry.get(key)
    if not isinstance(value, dict):
        return None
    nested = value.get(nested_key)
    if nested is None:
        return None
    text = str(nested).strip()
    return text or None


SEED_ITEMS, SEED_LOOKS = _load_seed_manifest(
    Path(__file__).resolve().parents[3] / "demo_assets" / "seed-manifest.json"
)
RETIRED_SEED_LOOK_KEYS = frozenset(
    {
        "weekend_denim",
        "city_commute",
        "evening_blue",
    }
)
RETIRED_SEED_ITEM_KEYS = frozenset(
    {
        "white_tank_top",
        "light_blue_jeans",
        "beige_blazer",
        "white_cable_sweater",
        "beige_trousers",
        "black_city_coat",
        "blue_evening_dress",
        "leather_shoes",
    }
)
SHOWCASE_SEED_ORDER = {
    item.key: order
    for order, item in enumerate(item for item in SEED_ITEMS if item.key.startswith("user_"))
}


def _seed_item_metadata(definition: SeedItem) -> dict[str, object]:
    metadata: dict[str, object] = {
        "annotation_provenance": "curated_seed",
        "review_state": "human_reviewed",
        "seed_key": definition.key,
        "source_ref": definition.source_ref,
        "asset_pair": {
            "real": definition.file_name,
            "pixel": definition.pixel_file_name,
            "source_real": definition.source_file_name,
            "source_pixel": definition.source_pixel_file_name,
        },
    }
    if definition.key in SHOWCASE_SEED_ORDER:
        metadata["showcase_order"] = SHOWCASE_SEED_ORDER[definition.key]
    return metadata


class CuratedDemoWardrobeBootstrapper:
    def __init__(
        self,
        *,
        captures: CaptureRepository,
        wardrobe: DemoWardrobeRepository,
        looks: DemoLookRepository,
        objects: DemoObjectWriter,
        assets_root: Path,
        item_presentations: DemoItemPresentationRepository | None = None,
        renders: DemoRenderArtifactRepository | None = None,
    ) -> None:
        self._captures = captures
        self._wardrobe = wardrobe
        self._looks = looks
        self._objects = objects
        self._assets_root = assets_root
        self._item_presentations = item_presentations
        self._renders = renders

    async def ensure_for_user(self, user_id: UUID) -> None:
        await self._remove_retired_seed_content(user_id)
        stored_items: dict[str, WardrobeItem] = {}
        for item_definition in SEED_ITEMS:
            stored_items[item_definition.key] = await self._ensure_item(
                user_id,
                item_definition,
            )
        for look_definition in SEED_LOOKS:
            await self._ensure_look(user_id, look_definition, stored_items)

    async def _remove_retired_seed_content(self, user_id: UUID) -> None:
        retired_selection_keys = {f"seed_{seed_key}" for seed_key in RETIRED_SEED_LOOK_KEYS}
        for look in await self._looks.list_for_user(user_id):
            if (
                look.source is LookSource.FEED_SAVED
                and look.source_selection_key in retired_selection_keys
            ):
                await self._looks.delete_for_user(
                    look.id,
                    user_id,
                    delete_items=True,
                )

        for item in await self._wardrobe.list_for_user(user_id):
            if (
                item.model_metadata.get("annotation_provenance") == "curated_seed"
                and item.model_metadata.get("seed_key") in RETIRED_SEED_ITEM_KEYS
            ):
                await self._wardrobe.delete_for_user(item.id, user_id)

    async def _ensure_item(self, user_id: UUID, definition: SeedItem) -> WardrobeItem:
        source_file_name = _seed_source_file_name(self._assets_root, definition)
        source_seed_image = _read_seed_image(
            self._assets_root / source_file_name,
            object_key=f"curated-seed/source/{source_file_name}",
        )
        display_seed_image = _read_seed_image(
            self._assets_root / definition.file_name,
            object_key=f"curated-seed/display/{definition.file_name}",
        )
        source_image = self._objects.write_private_source_image(
            source_seed_image,
            owner_id=user_id,
            prefix=f"originals/curated-seed/{user_id}/{definition.key}",
        )
        display_image = self._objects.write_derived_image(
            display_seed_image,
            owner_id=user_id,
            prefix=f"derived/curated-seed/{user_id}",
        )
        capture = Capture.create(
            user_id=user_id,
            source=CaptureSource(
                kind=(
                    CaptureSourceKind.UPLOAD
                    if definition.ownership is OwnershipState.OWNED
                    else CaptureSourceKind.FEED
                ),
                object_key=source_image.object_key,
                sha256=source_image.sha256,
                origin_ref=definition.source_ref,
            ),
            ownership=definition.ownership,
        )
        now = datetime.now(UTC)
        submitted = await self._captures.save_submission(
            capture,
            ProcessingJob(
                id=UUID(int=(capture.id.int ^ 1) % (1 << 128)),
                capture_id=capture.id,
                state=JobState.READY,
                attempt=1,
                created_at=now,
                updated_at=now,
            ),
            f"curated-seed:{definition.key}",
        )
        existing = await self._wardrobe.get_by_capture(submitted.capture.id)
        if existing is not None:
            updated = existing
            if (
                existing.model_metadata.get("annotation_provenance") == "curated_seed"
                and existing.display_object_key != display_image.object_key
            ):
                updated = updated.with_display_object(display_image.object_key)
            expected_metadata = _seed_item_metadata(definition)
            if any(
                updated.model_metadata.get(name) != value
                for name, value in expected_metadata.items()
            ):
                updated = updated.with_model_metadata(expected_metadata)
            if updated != existing:
                existing = await self._wardrobe.save(updated)
            await self._ensure_item_pixel(existing, definition)
            return existing
        fields = {
            "category": _seed_field(definition.category),
            "subcategory": _seed_field(definition.subcategory),
            "description": _seed_field(definition.name),
            "colors": _seed_field(list(definition.colors)),
            "styles": _seed_field(list(definition.styles)),
        }
        _add_seed_field(fields, "materials", list(definition.materials))
        _add_seed_field(fields, "pattern", definition.pattern)
        _add_seed_field(fields, "silhouette", definition.silhouette)
        _add_seed_field(fields, "fit", definition.fit)
        _add_seed_field(fields, "seasons", list(definition.seasons))
        _add_seed_field(fields, "occasions", list(definition.occasions))
        _add_seed_field(fields, "details", list(definition.details))
        item = WardrobeItem(
            id=UUID(int=(submitted.capture.id.int ^ 2) % (1 << 128)),
            user_id=user_id,
            capture_id=submitted.capture.id,
            selection_key="whole_capture",
            source_object_key=source_image.object_key,
            display_object_key=display_image.object_key,
            source_available=True,
            source_kind=submitted.capture.source.kind,
            ownership=definition.ownership,
            status=ItemStatus.READY,
            attributes=ItemAttributes(fields),
            model_metadata=_seed_item_metadata(definition),
            embedding=None,
            created_at=now,
            updated_at=now,
        )
        stored = await self._wardrobe.save(item)
        await self._ensure_item_pixel(stored, definition)
        return stored

    async def _ensure_item_pixel(
        self,
        item: WardrobeItem,
        definition: SeedItem,
    ) -> None:
        if self._item_presentations is None or definition.pixel_file_name is None:
            return
        pixel = _read_seed_image(
            self._assets_root / definition.pixel_file_name,
            object_key=f"curated-seed/{definition.pixel_file_name}",
        )
        stored_pixel = self._objects.write_derived_image(
            pixel,
            owner_id=item.user_id,
            prefix=f"derived/curated-seed/{item.user_id}/pixel-items",
        )
        signature = pixel_item_signature(item)
        requested = await self._item_presentations.ensure_requested(
            ItemPresentationAsset.queued(
                user_id=item.user_id,
                item_id=item.id,
                kind=ItemPresentationKind.PIXEL_ITEM,
                input_signature=signature,
                request_key=(
                    f"curated-seed:item-pixel:{definition.key}:"
                    f"{signature.version}:{signature.hash[:16]}"
                ),
            )
        )
        if requested.output is not None:
            return
        await self._item_presentations.save(
            requested.mark_succeeded(
                output=RenderOutput(
                    object_key=stored_pixel.object_key,
                    content_hash=stored_pixel.sha256,
                    content_type=stored_pixel.content_type,
                ),
                provider_trace=_curated_pixel_trace(),
            )
        )

    async def _ensure_look(
        self,
        user_id: UUID,
        definition: SeedLook,
        items: dict[str, WardrobeItem],
    ) -> None:
        component_items = tuple(items[key] for key in definition.item_keys)
        body = (self._assets_root / definition.file_name).read_bytes()
        digest = sha256(body).hexdigest()
        image = self._objects.write_derived_image(
            ImagePayload(
                object_key=f"curated-seed/{definition.file_name}",
                content_type=_seed_content_type(self._assets_root / definition.file_name),
                body=body,
                sha256=digest,
            ),
            owner_id=user_id,
            prefix=f"derived/curated-seed/{user_id}",
        )
        now = datetime.now(UTC)
        anchor = component_items[0]
        source_selection_key = f"seed_{definition.key}"
        look = await self._looks.get_by_capture(
            anchor.capture_id,
            source_selection_key,
        )
        if look is None:
            look = await self._looks.save(
                Look(
                    id=UUID(
                        int=(anchor.id.int ^ int.from_bytes(definition.key.encode())) % (1 << 128)
                    ),
                    user_id=user_id,
                    capture_id=anchor.capture_id,
                    source_selection_key=source_selection_key,
                    source=LookSource.FEED_SAVED,
                    status=LookStatus.READY,
                    analysis=_seed_analysis(definition),
                    display_object_key=image.object_key,
                    created_at=now,
                    updated_at=now,
                )
            )
        polygon = (
            NormalizedPoint(0.05, 0.05),
            NormalizedPoint(0.95, 0.05),
            NormalizedPoint(0.95, 0.95),
            NormalizedPoint(0.05, 0.95),
        )
        for index, item in enumerate(component_items):
            await self._looks.save_component(
                LookComponent.pending(
                    look_id=look.id,
                    component_key=f"seed_component_{index + 1}",
                    evidence_region=polygon,
                    confidence=1,
                    grounding_metadata={
                        "annotation_provenance": "curated_seed",
                        "source_ref": item.model_metadata["source_ref"],
                    },
                    role=str(item.attributes.fields["category"].value),
                    layer="main",
                    display_order=index,
                ).with_item(item.id)
            )
        await self._ensure_look_pixel(look, definition)

    async def _ensure_look_pixel(
        self,
        look: Look,
        definition: SeedLook,
    ) -> None:
        if self._renders is None or definition.pixel_file_name is None:
            return
        pixel = _read_seed_image(
            self._assets_root / definition.pixel_file_name,
            object_key=f"curated-seed/{definition.pixel_file_name}",
        )
        stored_pixel = self._objects.write_derived_image(
            pixel,
            owner_id=look.user_id,
            prefix=f"derived/curated-seed/{look.user_id}/pixel-looks",
        )
        signature = RenderInputSignature(
            version="curated-look-pixel-v1",
            hash=sha256(
                f"{definition.key}:{stored_pixel.sha256}:{look.updated_at.isoformat()}".encode()
            ).hexdigest(),
        )
        requested = await self._renders.ensure_requested(
            RenderArtifact.queued(
                user_id=look.user_id,
                look_id=look.id,
                kind=RenderArtifactKind.PIXEL_COVER,
                input_signature=signature,
                request_key=f"curated-seed:look-pixel:{definition.key}",
                privacy=RenderPrivacy.SHAREABLE_PIXEL,
                provider_trace=_curated_pixel_trace(),
            )
        )
        if requested.output is not None:
            return
        await self._renders.save(
            requested.mark_succeeded(
                RenderOutput(
                    object_key=stored_pixel.object_key,
                    content_hash=stored_pixel.sha256,
                    content_type=stored_pixel.content_type,
                )
            )
        )


def _seed_field(value: object) -> FieldEnvelope:
    return FieldEnvelope(
        value=value,
        provenance=FieldProvenance.CURATED_SEED,
        confidence=1,
        model_version=None,
        locked=False,
    )


def _add_seed_field(fields: dict[str, FieldEnvelope], name: str, value: object) -> None:
    if value in (None, "", []):
        return
    fields[name] = _seed_field(value)


def _read_seed_image(path: Path, *, object_key: str) -> ImagePayload:
    body = path.read_bytes()
    return ImagePayload(
        object_key=object_key,
        content_type=_seed_content_type(path),
        body=body,
        sha256=sha256(body).hexdigest(),
    )


def _seed_source_file_name(assets_root: Path, definition: SeedItem) -> str:
    if (
        definition.source_file_name is not None
        and (assets_root / definition.source_file_name).is_file()
    ):
        return definition.source_file_name
    return definition.file_name


def _seed_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    raise ValueError(f"unsupported curated seed image type: {path.name}")


def _curated_pixel_trace() -> RenderProviderTrace:
    return RenderProviderTrace(
        provider="curated_seed",
        model="image_generation",
        parameters={
            "annotation_provenance": "curated_seed",
            "review_state": "human_reviewed",
        },
    )


def _seed_analysis(definition: SeedLook) -> LookAnalysis:
    def field(value: str) -> LookAnalysisField:
        return LookAnalysisField(value=value, confidence=1)

    return LookAnalysis(
        color=field("经过人工复核的示例配色"),
        silhouette=field("轮廓比例清晰"),
        material=field("材质轻重有对比"),
        layering=field(definition.layering),
        focal_point=field(definition.title),
        scene=field(definition.scene),
        style=field(definition.style),
        metadata=LookAnalysisMetadata(
            capability_alias="curated_seed",
            model_version="human_reviewed",
            prompt_version="not_applicable",
            schema_version="look_analysis_v1",
            taxonomy_version="wardrobe_taxonomy_v1",
            latency_ms=0,
        ),
    )
