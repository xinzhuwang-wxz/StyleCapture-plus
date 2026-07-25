from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.domain import Capture, ImagePayload, ProcessingJob
from stylecapture_backend.features.capture.ports import CaptureSubmission
from stylecapture_backend.features.look.domain import Look, LookComponent
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
            object_key=f"{prefix}/{image.sha256}.jpg",
            content_type=image.content_type,
            body=image.body,
            sha256=image.sha256,
        )


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
