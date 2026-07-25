from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.domain import Capture, ImagePayload, ProcessingJob
from stylecapture_backend.features.capture.ports import CaptureSubmission
from stylecapture_backend.features.item_presentation.domain import ItemPresentationAsset
from stylecapture_backend.features.look.domain import Look, LookComponent
from stylecapture_backend.features.render.domain import RenderArtifact
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

    async def save(self, look: Look) -> Look:
        self.save_calls += 1
        capture_id = cast(UUID, look.capture_id)
        self.looks[(capture_id, look.source_selection_key)] = look
        return look

    async def save_component(self, component: LookComponent) -> LookComponent:
        return component


class MemoryObjects:
    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload:
        return ImagePayload(
            object_key=f"{prefix}/{image.sha256}{Path(image.object_key).suffix}",
            content_type=image.content_type,
            body=image.body,
            sha256=image.sha256,
        )


class MemoryItemPresentations:
    def __init__(self) -> None:
        self.assets: dict[tuple[UUID, str], ItemPresentationAsset] = {}

    async def ensure_requested(
        self,
        asset: ItemPresentationAsset,
    ) -> ItemPresentationAsset:
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
    assets_root = (
        Path(curated_demo.__file__).resolve().parents[3] / "demo_assets"
    )

    assert len(curated_demo.SEED_ITEMS) == 10
    assert len(curated_demo.SEED_LOOKS) == 3
    for item in curated_demo.SEED_ITEMS:
        assert (assets_root / item.file_name).is_file()
        assert item.pixel_file_name is not None
        assert (assets_root / item.pixel_file_name).is_file()
    for look in curated_demo.SEED_LOOKS:
        assert (assets_root / look.file_name).is_file()
        assert look.pixel_file_name is not None
        assert (assets_root / look.pixel_file_name).is_file()


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
                style=("温柔",),
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
                style=("温柔",),
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
    bootstrapper = CuratedDemoWardrobeBootstrapper(
        captures=MemoryCaptures(),  # type: ignore[arg-type]
        wardrobe=MemoryWardrobe(),
        looks=MemoryLooks(),
        objects=MemoryObjects(),
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
