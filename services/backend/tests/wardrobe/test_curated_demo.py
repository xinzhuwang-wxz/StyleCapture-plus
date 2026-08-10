from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.domain import Capture, ImagePayload, ProcessingJob
from stylecapture_backend.features.capture.ports import CaptureSubmission
from stylecapture_backend.features.item_presentation.domain import ItemPresentationAsset
from stylecapture_backend.features.item_presentation.ports import (
    ItemPresentationIdempotencyConflict,
)
from stylecapture_backend.features.look.domain import Look, LookComponent, LookDeletionResult
from stylecapture_backend.features.render.domain import RenderArtifact
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.features.wardrobe.domain import WardrobeItem
from stylecapture_backend.features.wardrobe.infrastructure import curated_demo
from stylecapture_backend.features.wardrobe.infrastructure.curated_demo import (
    CuratedDemoWardrobeBootstrapper,
    SeedItem,
    SeedLook,
)


class MemoryCaptures:
    def __init__(self) -> None:
        self.submissions: dict[tuple[UUID, str], CaptureSubmission] = {}

    async def save_submission(
        self,
        capture: Capture,
        job: ProcessingJob,
        idempotency_key: str,
    ) -> CaptureSubmission:
        identity = (capture.user_id, idempotency_key)
        if identity not in self.submissions:
            self.submissions[identity] = CaptureSubmission(capture=capture, job=job)
        return self.submissions[identity]


class MemoryWardrobe:
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, str], WardrobeItem] = {}

    async def get_by_capture(
        self,
        capture_id: UUID,
        selection_key: str = "whole_capture",
    ) -> WardrobeItem | None:
        return self.items.get((capture_id, selection_key))

    async def save(self, item: WardrobeItem) -> WardrobeItem:
        self.items[(item.capture_id, item.selection_key)] = item
        return item

    async def list_for_user(self, user_id: UUID) -> list[WardrobeItem]:
        return [item for item in self.items.values() if item.user_id == user_id]

    async def get_for_user(self, item_id: UUID, user_id: UUID) -> WardrobeItem | None:
        for item in self.items.values():
            if item.id == item_id and item.user_id == user_id:
                return item
        return None

    async def save_user_state(self, item: WardrobeItem) -> WardrobeItem:
        return await self.save(item)

    async def delete_for_user(self, item_id: UUID, user_id: UUID) -> bool:
        identity = next(
            (
                key
                for key, item in self.items.items()
                if item.id == item_id and item.user_id == user_id
            ),
            None,
        )
        if identity is None:
            return False
        del self.items[identity]
        return True


class MemoryLooks:
    def __init__(self) -> None:
        self.looks: dict[tuple[UUID, str], Look] = {}
        self.save_calls = 0

    async def get_by_capture(
        self,
        capture_id: UUID,
        source_selection_key: str,
    ) -> Look | None:
        return self.looks.get((capture_id, source_selection_key))

    async def list_for_user(self, user_id: UUID) -> list[Look]:
        return [look for look in self.looks.values() if look.user_id == user_id]

    async def save(self, look: Look) -> Look:
        self.save_calls += 1
        capture_id = cast(UUID, look.capture_id)
        self.looks[(capture_id, look.source_selection_key)] = look
        return look

    async def save_component(self, component: LookComponent) -> LookComponent:
        return component

    async def delete_for_user(
        self,
        look_id: UUID,
        user_id: UUID,
        *,
        delete_items: bool,
    ) -> LookDeletionResult | None:
        identity = next(
            (
                key
                for key, look in self.looks.items()
                if look.id == look_id and look.user_id == user_id
            ),
            None,
        )
        if identity is None:
            return None
        del self.looks[identity]
        return LookDeletionResult(
            look_id=look_id,
            deleted_item_ids=(),
            preserved_shared_item_ids=(),
        )


class MemoryObjects:
    def __init__(self) -> None:
        self.images: list[ImagePayload] = []

    def write_private_source_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload:
        return self._write_image(image, prefix=prefix)

    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload:
        return self._write_image(image, prefix=prefix)

    def _write_image(self, image: ImagePayload, *, prefix: str) -> ImagePayload:
        stored = ImagePayload(
            object_key=f"{prefix}/{image.sha256}{Path(image.object_key).suffix}",
            content_type=image.content_type,
            body=image.body,
            sha256=image.sha256,
        )
        self.images.append(stored)
        return stored


class MemorySourceStore:
    def __init__(self, images: list[ImagePayload]) -> None:
        self.images = {image.object_key: image for image in images}
        self.deleted: set[str] = set()

    def read_image(self, object_key: str) -> ImagePayload:
        if object_key in self.deleted:
            raise FileNotFoundError(object_key)
        return self.images[object_key]

    def delete(self, object_key: str) -> None:
        self.deleted.add(object_key)


class MemoryItemPresentations:
    def __init__(self) -> None:
        self.assets: dict[tuple[UUID, str], ItemPresentationAsset] = {}

    async def ensure_requested(
        self,
        asset: ItemPresentationAsset,
    ) -> ItemPresentationAsset:
        existing_request = next(
            (
                existing
                for existing in self.assets.values()
                if existing.user_id == asset.user_id and existing.request_key == asset.request_key
            ),
            None,
        )
        if existing_request is not None:
            if existing_request.input_signature != asset.input_signature:
                raise ItemPresentationIdempotencyConflict(
                    "request key already represents another curated pixel signature"
                )
            return existing_request
        identity = (asset.item_id, asset.request_key)
        return self.assets.setdefault(identity, asset)

    async def save(self, asset: ItemPresentationAsset) -> ItemPresentationAsset:
        self.assets[(asset.item_id, asset.request_key)] = asset
        return asset


class MemoryRenders:
    def __init__(self) -> None:
        self.artifacts: dict[tuple[UUID, str], RenderArtifact] = {}

    async def ensure_requested(self, artifact: RenderArtifact) -> RenderArtifact:
        identity = (artifact.look_id, artifact.request_key)
        return self.artifacts.setdefault(identity, artifact)

    async def save(self, artifact: RenderArtifact) -> RenderArtifact:
        self.artifacts[(artifact.look_id, artifact.request_key)] = artifact
        return artifact


def test_curated_manifest_tracks_real_and_pixel_assets() -> None:
    assets_root = Path(curated_demo.__file__).resolve().parents[3] / "demo_assets"

    assert len(curated_demo.SEED_ITEMS) == 20
    assert len(curated_demo.SEED_LOOKS) == 6
    assert curated_demo.RETIRED_SEED_ITEM_KEYS.isdisjoint(
        item.key for item in curated_demo.SEED_ITEMS
    )
    assert curated_demo.RETIRED_SEED_LOOK_KEYS.isdisjoint(
        look.key for look in curated_demo.SEED_LOOKS
    )
    for item in curated_demo.SEED_ITEMS:
        assert (assets_root / item.file_name).is_file()
        assert item.pixel_file_name is not None
        assert (assets_root / item.pixel_file_name).is_file()
    for look in curated_demo.SEED_LOOKS:
        assert (assets_root / look.file_name).is_file()
        assert look.pixel_file_name is not None
        assert (assets_root / look.pixel_file_name).is_file()


@pytest.mark.asyncio
async def test_bootstrap_removes_only_retired_seed_content_for_existing_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for file_name in ("retired-item.jpg", "active-item.jpg", "retired-look.jpg", "active-look.jpg"):
        (tmp_path / file_name).write_bytes(file_name.encode())
    retired_item = SeedItem(
        key="white_tank_top",
        file_name="retired-item.jpg",
        name="已下线单品",
        category="tops",
        subcategory="背心",
        ownership=curated_demo.OwnershipState.OWNED,
        colors=("白色",),
        styles=("休闲",),
        source_ref="https://example.test/retired",
    )
    active_item = SeedItem(
        key="active_top",
        file_name="active-item.jpg",
        name="保留单品",
        category="tops",
        subcategory="上衣",
        ownership=curated_demo.OwnershipState.OWNED,
        colors=("黑色",),
        styles=("通勤",),
        source_ref="https://example.test/active",
    )
    retired_look = SeedLook(
        key="weekend_denim",
        file_name="retired-look.jpg",
        title="已下线穿搭",
        item_keys=(retired_item.key,),
        scene="周末",
        style="休闲",
        layering="单层",
    )
    active_look = SeedLook(
        key="active_look",
        file_name="active-look.jpg",
        title="保留穿搭",
        item_keys=(active_item.key,),
        scene="通勤",
        style="简约",
        layering="单层",
    )
    wardrobe = MemoryWardrobe()
    looks = MemoryLooks()
    bootstrapper = CuratedDemoWardrobeBootstrapper(
        captures=MemoryCaptures(),  # type: ignore[arg-type]
        wardrobe=wardrobe,
        looks=looks,
        objects=MemoryObjects(),
        assets_root=tmp_path,
    )
    user_id = uuid4()

    monkeypatch.setattr(curated_demo, "RETIRED_SEED_ITEM_KEYS", frozenset())
    monkeypatch.setattr(curated_demo, "RETIRED_SEED_LOOK_KEYS", frozenset())
    monkeypatch.setattr(curated_demo, "SEED_ITEMS", (retired_item, active_item))
    monkeypatch.setattr(curated_demo, "SEED_LOOKS", (retired_look, active_look))
    await bootstrapper.ensure_for_user(user_id)

    monkeypatch.setattr(curated_demo, "RETIRED_SEED_ITEM_KEYS", frozenset({retired_item.key}))
    monkeypatch.setattr(curated_demo, "RETIRED_SEED_LOOK_KEYS", frozenset({retired_look.key}))
    monkeypatch.setattr(curated_demo, "SEED_ITEMS", ())
    monkeypatch.setattr(curated_demo, "SEED_LOOKS", ())
    await bootstrapper.ensure_for_user(user_id)

    assert {item.model_metadata["seed_key"] for item in wardrobe.items.values()} == {
        active_item.key
    }
    assert {look.source_selection_key for look in looks.looks.values()} == {
        f"seed_{active_look.key}"
    }


def test_user_curated_items_have_searchable_tags_and_source_pairing() -> None:
    user_items = [item for item in curated_demo.SEED_ITEMS if item.key.startswith("user_")]

    assert len(user_items) == 18
    for item in user_items:
        assert item.ownership is curated_demo.OwnershipState.OWNED
        assert item.file_name.startswith("user-items/")
        assert item.pixel_file_name is not None
        assert item.pixel_file_name.startswith("pixel-items/user-items/")
        assert item.source_ref.startswith("local-curated-seed:single-item-presets/")
        assert item.source_file_name is not None
        assert item.source_pixel_file_name is not None
        assert item.colors
        assert item.materials
        assert item.styles
        assert item.seasons
        assert item.occasions
        assert item.details
        assert item.pattern is not None
        assert item.silhouette is not None
        assert item.fit is not None


@pytest.mark.asyncio
async def test_reopening_a_session_does_not_mutate_curated_look_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "top.jpg").write_bytes(b"curated top")
    (tmp_path / "look.jpg").write_bytes(b"curated look")
    monkeypatch.setattr(
        curated_demo,
        "SEED_ITEMS",
        (
            SeedItem(
                key="top",
                file_name="top.jpg",
                name="示例上衣",
                category="tops",
                subcategory="针织衫",
                ownership=curated_demo.OwnershipState.OWNED,
                colors=("象牙白",),
                styles=("温柔",),
                source_ref="https://example.test/top",
            ),
        ),
    )
    monkeypatch.setattr(
        curated_demo,
        "SEED_LOOKS",
        (
            SeedLook(
                key="look",
                file_name="look.jpg",
                title="示例穿搭",
                item_keys=("top",),
                scene="通勤",
                style="简约",
                layering="单层",
            ),
        ),
    )
    looks = MemoryLooks()
    bootstrapper = CuratedDemoWardrobeBootstrapper(
        captures=MemoryCaptures(),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobe(),
        looks=looks,
        objects=MemoryObjects(),
        assets_root=tmp_path,
    )
    user_id = uuid4()

    await bootstrapper.ensure_for_user(user_id)
    first = next(iter(looks.looks.values()))
    await bootstrapper.ensure_for_user(user_id)
    second = next(iter(looks.looks.values()))

    assert looks.save_calls == 1
    assert second.updated_at == first.updated_at


@pytest.mark.asyncio
async def test_bootstrap_imports_pixel_assets_without_runtime_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "top.jpg").write_bytes(b"curated top")
    (tmp_path / "top.png").write_bytes(b"curated top pixel")
    (tmp_path / "look.jpg").write_bytes(b"curated look")
    (tmp_path / "look.png").write_bytes(b"curated look pixel")
    monkeypatch.setattr(
        curated_demo,
        "SEED_ITEMS",
        (
            SeedItem(
                key="top",
                file_name="top.jpg",
                pixel_file_name="top.png",
                name="示例上衣",
                category="tops",
                subcategory="针织衫",
                ownership=curated_demo.OwnershipState.OWNED,
                colors=("象牙白",),
                styles=("温柔",),
                source_ref="https://example.test/top",
            ),
        ),
    )
    monkeypatch.setattr(
        curated_demo,
        "SEED_LOOKS",
        (
            SeedLook(
                key="look",
                file_name="look.jpg",
                pixel_file_name="look.png",
                title="示例穿搭",
                item_keys=("top",),
                scene="通勤",
                style="简约",
                layering="单层",
            ),
        ),
    )
    presentations = MemoryItemPresentations()
    renders = MemoryRenders()
    objects = MemoryObjects()
    bootstrapper = CuratedDemoWardrobeBootstrapper(
        captures=MemoryCaptures(),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobe(),
        looks=MemoryLooks(),
        objects=objects,
        assets_root=tmp_path,
        item_presentations=presentations,
        renders=renders,
    )
    user_id = uuid4()

    await bootstrapper.ensure_for_user(user_id)
    await bootstrapper.ensure_for_user(user_id)

    assert len(presentations.assets) == 1
    item_pixel = next(iter(presentations.assets.values()))
    assert item_pixel.output is not None
    assert item_pixel.output.content_type == "image/png"
    assert item_pixel.provider_trace is not None
    assert item_pixel.provider_trace.provider == "curated_seed"
    assert len(renders.artifacts) == 1
    look_pixel = next(iter(renders.artifacts.values()))
    assert look_pixel.output is not None
    assert look_pixel.output.content_type == "image/png"
    assert look_pixel.share_eligible
    assert [image.content_type for image in objects.images[:4]] == [
        "image/jpeg",
        "image/jpeg",
        "image/png",
        "image/jpeg",
    ]
    assert objects.images[4].content_type == "image/png"
    assert len({image.object_key for image in objects.images}) == 5


@pytest.mark.asyncio
async def test_bootstrap_stores_user_seed_tags_and_png_source() -> None:
    source = next(
        item for item in curated_demo.SEED_ITEMS if item.key == "user_blue_yellow_print_dress"
    )
    captures = MemoryCaptures()
    wardrobe = MemoryWardrobe()
    objects = MemoryObjects()
    presentations = MemoryItemPresentations()
    bootstrapper = CuratedDemoWardrobeBootstrapper(
        captures=captures,  # type: ignore[arg-type]
        wardrobe=wardrobe,
        looks=MemoryLooks(),
        objects=objects,
        assets_root=Path(curated_demo.__file__).resolve().parents[3] / "demo_assets",
        item_presentations=presentations,
    )
    monkeypatch_items = (source,)
    original_items = curated_demo.SEED_ITEMS
    original_looks = curated_demo.SEED_LOOKS
    curated_demo.SEED_ITEMS = monkeypatch_items
    curated_demo.SEED_LOOKS = ()
    try:
        await bootstrapper.ensure_for_user(uuid4())
    finally:
        curated_demo.SEED_ITEMS = original_items
        curated_demo.SEED_LOOKS = original_looks

    stored = next(iter(wardrobe.items.values()))
    assert objects.images[0].content_type == "image/png"
    assert objects.images[1].content_type == "image/png"
    assert stored.source_object_key != stored.display_object_key
    assert stored.ownership is curated_demo.OwnershipState.OWNED
    assert (
        stored.attributes.fields["styles"].provenance is curated_demo.FieldProvenance.CURATED_SEED
    )
    assert stored.attributes.fields["materials"].value == ["轻薄梭织", "雪纺感面料"]
    assert stored.attributes.fields["pattern"].value == "抽象花卉印花"
    assert stored.attributes.fields["seasons"].value == ["夏季", "春季"]
    assert stored.model_metadata["annotation_provenance"] == "curated_seed"
    assert stored.model_metadata["seed_key"] == "user_blue_yellow_print_dress"
    assert stored.model_metadata["showcase_order"] == 0
    assert stored.model_metadata["asset_pair"] == {
        "real": "user-items/blue-yellow-print-dress.png",
        "pixel": "pixel-items/user-items/blue-yellow-print-dress.png",
        "source_real": "单品01_蓝黄印花连衣裙_实物.png",
        "source_pixel": "单品01_蓝黄印花连衣裙_像素.png",
    }
    item_pixel = next(iter(presentations.assets.values()))
    assert item_pixel.output is not None
    assert item_pixel.output.content_type == "image/png"


@pytest.mark.asyncio
async def test_curated_seed_display_survives_source_deletion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "source.png").write_bytes(b"source evidence")
    (tmp_path / "display.png").write_bytes(b"display asset")
    monkeypatch.setattr(
        curated_demo,
        "SEED_ITEMS",
        (
            SeedItem(
                key="top",
                file_name="display.png",
                source_file_name="source.png",
                name="示例上衣",
                category="tops",
                subcategory="针织衫",
                ownership=curated_demo.OwnershipState.OWNED,
                colors=("象牙白",),
                styles=("温柔",),
                source_ref="local-curated-seed:test",
            ),
        ),
    )
    monkeypatch.setattr(curated_demo, "SEED_LOOKS", ())
    wardrobe = MemoryWardrobe()
    objects = MemoryObjects()
    bootstrapper = CuratedDemoWardrobeBootstrapper(
        captures=MemoryCaptures(),  # type: ignore[arg-type]
        wardrobe=wardrobe,
        looks=MemoryLooks(),
        objects=objects,
        assets_root=tmp_path,
    )
    user_id = uuid4()

    await bootstrapper.ensure_for_user(user_id)
    item = next(iter(wardrobe.items.values()))
    application = WardrobeApplication(
        wardrobe=wardrobe,
        sources=MemorySourceStore(objects.images),
    )
    await application.delete_source(user_id, item.id)
    display = await application.read_display(user_id, item.id)

    assert item.source_object_key != item.display_object_key
    assert display.object_key == item.display_object_key
    assert display.body == b"display asset"


@pytest.mark.asyncio
async def test_curated_seed_reused_source_images_keep_distinct_source_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "shared-source.png").write_bytes(b"same original image")
    (tmp_path / "display-a.png").write_bytes(b"display a")
    (tmp_path / "display-b.png").write_bytes(b"display b")
    monkeypatch.setattr(
        curated_demo,
        "SEED_ITEMS",
        (
            SeedItem(
                key="shared_a",
                file_name="display-a.png",
                source_file_name="shared-source.png",
                name="共享来源 A",
                category="tops",
                subcategory="衬衫",
                ownership=curated_demo.OwnershipState.OWNED,
                colors=("白色",),
                styles=("通勤",),
                source_ref="local-curated-seed:shared-a",
            ),
            SeedItem(
                key="shared_b",
                file_name="display-b.png",
                source_file_name="shared-source.png",
                name="共享来源 B",
                category="bottoms",
                subcategory="短裙",
                ownership=curated_demo.OwnershipState.OWNED,
                colors=("黑色",),
                styles=("通勤",),
                source_ref="local-curated-seed:shared-b",
            ),
        ),
    )
    monkeypatch.setattr(curated_demo, "SEED_LOOKS", ())
    wardrobe = MemoryWardrobe()
    objects = MemoryObjects()
    bootstrapper = CuratedDemoWardrobeBootstrapper(
        captures=MemoryCaptures(),  # type: ignore[arg-type]
        wardrobe=wardrobe,
        looks=MemoryLooks(),
        objects=objects,
        assets_root=tmp_path,
    )
    user_id = uuid4()

    await bootstrapper.ensure_for_user(user_id)

    source_keys = {item.source_object_key for item in wardrobe.items.values()}
    assert len(source_keys) == 2
    assert any(f"originals/curated-seed/{user_id}/shared_a/" in key for key in source_keys)
    assert any(f"originals/curated-seed/{user_id}/shared_b/" in key for key in source_keys)


@pytest.mark.asyncio
async def test_curated_seed_reensure_upgrades_stale_display_without_overwriting_user_tags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "source.png").write_bytes(b"source evidence")
    (tmp_path / "display-v1.png").write_bytes(b"old display")
    (tmp_path / "display-v2.png").write_bytes(b"new manifest display")
    (tmp_path / "pixel.png").write_bytes(b"curated pixel")
    seed_v1 = SeedItem(
        key="top",
        file_name="display-v1.png",
        pixel_file_name="pixel.png",
        source_file_name="source.png",
        name="示例上衣",
        category="tops",
        subcategory="针织衫",
        ownership=curated_demo.OwnershipState.OWNED,
        colors=("象牙白",),
        styles=("温柔",),
        source_ref="local-curated-seed:test",
    )
    seed_v2 = SeedItem(
        key="top",
        file_name="display-v2.png",
        pixel_file_name="pixel.png",
        source_file_name="source.png",
        name="示例上衣",
        category="tops",
        subcategory="针织衫",
        ownership=curated_demo.OwnershipState.OWNED,
        colors=("象牙白",),
        styles=("温柔",),
        source_ref="local-curated-seed:test",
    )
    wardrobe = MemoryWardrobe()
    objects = MemoryObjects()
    presentations = MemoryItemPresentations()
    bootstrapper = CuratedDemoWardrobeBootstrapper(
        captures=MemoryCaptures(),  # type: ignore[arg-type]
        wardrobe=wardrobe,
        looks=MemoryLooks(),
        objects=objects,
        assets_root=tmp_path,
        item_presentations=presentations,
    )
    user_id = uuid4()
    monkeypatch.setattr(curated_demo, "SEED_LOOKS", ())
    monkeypatch.setattr(curated_demo, "SEED_ITEMS", (seed_v1,))
    await bootstrapper.ensure_for_user(user_id)
    stored = next(iter(wardrobe.items.values()))
    old_display_key = stored.display_object_key
    corrected = stored.correct("category", "outerwear")
    await wardrobe.save(corrected)

    monkeypatch.setattr(curated_demo, "SEED_ITEMS", (seed_v2,))
    await bootstrapper.ensure_for_user(user_id)
    upgraded = next(iter(wardrobe.items.values()))

    assert old_display_key != upgraded.display_object_key
    assert upgraded.display_object_key is not None
    assert upgraded.display_object_key.endswith(".png")
    assert upgraded.attributes.fields["category"].value == "outerwear"
    assert upgraded.attributes.fields["category"].provenance is curated_demo.FieldProvenance.USER
    assert len(presentations.assets) == 2
