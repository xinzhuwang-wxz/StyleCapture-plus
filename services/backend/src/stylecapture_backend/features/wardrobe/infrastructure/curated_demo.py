from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol
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
from stylecapture_backend.features.look.domain import (
    Look,
    LookAnalysis,
    LookAnalysisField,
    LookAnalysisMetadata,
    LookComponent,
    LookSource,
    LookStatus,
)
from stylecapture_backend.features.wardrobe.domain import (
    FieldEnvelope,
    FieldProvenance,
    ItemAttributes,
    ItemStatus,
    WardrobeItem,
)


class DemoWardrobeRepository(Protocol):
    async def get_by_capture(
        self,
        capture_id: UUID,
        selection_key: str = "whole_capture",
    ) -> WardrobeItem | None: ...

    async def save(self, item: WardrobeItem) -> WardrobeItem: ...


class DemoLookRepository(Protocol):
    async def get_by_capture(
        self,
        capture_id: UUID,
        source_selection_key: str,
    ) -> Look | None: ...

    async def save(self, look: Look) -> Look: ...

    async def save_component(self, component: LookComponent) -> LookComponent: ...


class DemoObjectWriter(Protocol):
    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload: ...


@dataclass(frozen=True, slots=True)
class SeedItem:
    key: str
    file_name: str
    name: str
    category: str
    subcategory: str
    ownership: OwnershipState
    colors: tuple[str, ...]
    style: tuple[str, ...]
    source_ref: str


@dataclass(frozen=True, slots=True)
class SeedLook:
    key: str
    file_name: str
    title: str
    item_keys: tuple[str, ...]
    scene: str
    style: str
    layering: str


SEED_ITEMS = (
    SeedItem(
        "white_cable_sweater",
        "white-cable-sweater.jpg",
        "象牙白绞花针织衫",
        "tops",
        "针织衫",
        OwnershipState.OWNED,
        ("象牙白",),
        ("温柔", "松弛", "秋冬"),
        "https://www.pexels.com/video/7576121/",
    ),
    SeedItem(
        "white_tank_top",
        "white-tank-top.jpg",
        "白色短款背心",
        "tops",
        "背心",
        OwnershipState.OWNED,
        ("白色",),
        ("简洁", "休闲", "夏日"),
        "https://www.pexels.com/video/7760056/",
    ),
    SeedItem(
        "light_blue_jeans",
        "light-blue-jeans.jpg",
        "浅蓝高腰直筒牛仔裤",
        "bottoms",
        "牛仔裤",
        OwnershipState.OWNED,
        ("浅蓝",),
        ("休闲", "复古", "日常"),
        "https://www.pexels.com/video/7760056/",
    ),
    SeedItem(
        "beige_blazer",
        "beige-blazer.jpg",
        "燕麦色垂感西装",
        "outerwear",
        "西装",
        OwnershipState.INSPIRATION,
        ("燕麦色",),
        ("通勤", "利落", "极简"),
        "https://www.pexels.com/video/7681932/",
    ),
    SeedItem(
        "beige_trousers",
        "beige-trousers.jpg",
        "燕麦色高腰西裤",
        "bottoms",
        "西裤",
        OwnershipState.INSPIRATION,
        ("燕麦色",),
        ("通勤", "利落", "极简"),
        "https://www.pexels.com/video/7681932/",
    ),
    SeedItem(
        "black_city_coat",
        "black-city-coat.jpg",
        "黑色廓形城市大衣",
        "outerwear",
        "大衣",
        OwnershipState.OWNED,
        ("黑色",),
        ("城市", "通勤", "冷静"),
        "https://www.pexels.com/video/5901084/",
    ),
    SeedItem(
        "plaid_scarf_blazer",
        "plaid-scarf-blazer.jpg",
        "格纹围巾与黑色短西装",
        "accessories",
        "围巾",
        OwnershipState.INSPIRATION,
        ("黑色", "灰色"),
        ("知性", "层次", "通勤"),
        "https://www.pexels.com/video/30789824/",
    ),
    SeedItem(
        "blue_evening_dress",
        "blue-evening-dress.jpg",
        "宝蓝亮片晚装裙",
        "dresses",
        "晚装裙",
        OwnershipState.INSPIRATION,
        ("宝蓝",),
        ("华丽", "聚会", "吸睛"),
        "https://www.pexels.com/video/15396483/",
    ),
    SeedItem(
        "leather_shoes",
        "leather-shoes.jpg",
        "黑色通勤皮鞋",
        "shoes",
        "皮鞋",
        OwnershipState.OWNED,
        ("黑色",),
        ("通勤", "耐穿", "中性"),
        "https://www.pexels.com/video/8322396/",
    ),
    SeedItem(
        "summer_accessories",
        "summer-accessories.jpg",
        "度假编织配饰组",
        "accessories",
        "配饰组",
        OwnershipState.INSPIRATION,
        ("草编色", "绿色"),
        ("度假", "自然", "夏日"),
        "https://www.pexels.com/video/5405659/",
    ),
)

SEED_LOOKS = (
    SeedLook(
        "weekend_denim",
        "look-weekend-denim.jpg",
        "周末蓝调",
        ("white_tank_top", "light_blue_jeans", "beige_blazer", "leather_shoes"),
        "周末逛展与轻松约会",
        "简洁复古休闲",
        "短上衣提高腰线, 垂感外套平衡牛仔裤的休闲感",
    ),
    SeedLook(
        "city_commute",
        "look-city-commute.jpg",
        "城市燕麦拿铁",
        ("white_cable_sweater", "beige_trousers", "black_city_coat", "leather_shoes"),
        "通勤、面试与城市行走",
        "克制利落通勤",
        "同色系内搭拉长纵向比例, 黑色外套建立清晰轮廓",
    ),
    SeedLook(
        "evening_blue",
        "look-evening-blue.jpg",
        "蓝色高光时刻",
        ("blue_evening_dress", "leather_shoes", "summer_accessories"),
        "晚宴、派对与重要合影",
        "华丽聚会风",
        "单一高饱和焦点承担当晚主角, 其余配饰降低存在感",
    ),
)


class CuratedDemoWardrobeBootstrapper:
    def __init__(
        self,
        *,
        captures: CaptureRepository,
        wardrobe: DemoWardrobeRepository,
        looks: DemoLookRepository,
        objects: DemoObjectWriter,
        assets_root: Path,
    ) -> None:
        self._captures = captures
        self._wardrobe = wardrobe
        self._looks = looks
        self._objects = objects
        self._assets_root = assets_root

    async def ensure_for_user(self, user_id: UUID) -> None:
        stored_items: dict[str, WardrobeItem] = {}
        for item_definition in SEED_ITEMS:
            stored_items[item_definition.key] = await self._ensure_item(
                user_id,
                item_definition,
            )
        for look_definition in SEED_LOOKS:
            await self._ensure_look(user_id, look_definition, stored_items)

    async def _ensure_item(self, user_id: UUID, definition: SeedItem) -> WardrobeItem:
        body = (self._assets_root / definition.file_name).read_bytes()
        digest = sha256(body).hexdigest()
        image = self._objects.write_derived_image(
            ImagePayload(
                object_key=f"curated-seed/{definition.file_name}",
                content_type="image/jpeg",
                body=body,
                sha256=digest,
            ),
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
                object_key=image.object_key,
                sha256=image.sha256,
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
            return existing
        fields = {
            "category": _seed_field(definition.category),
            "subcategory": _seed_field(definition.subcategory),
            "description": _seed_field(definition.name),
            "colors": _seed_field(list(definition.colors)),
            "style": _seed_field(list(definition.style)),
        }
        item = WardrobeItem(
            id=UUID(int=(submitted.capture.id.int ^ 2) % (1 << 128)),
            user_id=user_id,
            capture_id=submitted.capture.id,
            selection_key="whole_capture",
            source_object_key=image.object_key,
            display_object_key=image.object_key,
            source_available=True,
            source_kind=submitted.capture.source.kind,
            ownership=definition.ownership,
            status=ItemStatus.READY,
            attributes=ItemAttributes(fields),
            model_metadata={
                "annotation_provenance": "curated_seed",
                "review_state": "human_reviewed",
                "source_ref": definition.source_ref,
            },
            embedding=None,
            created_at=now,
            updated_at=now,
        )
        return await self._wardrobe.save(item)

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
                content_type="image/jpeg",
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


def _seed_field(value: object) -> FieldEnvelope:
    return FieldEnvelope(
        value=value,
        provenance=FieldProvenance.CURATED_SEED,
        confidence=1,
        model_version=None,
        locked=False,
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
