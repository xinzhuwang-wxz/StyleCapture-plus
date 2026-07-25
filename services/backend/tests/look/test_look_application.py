from __future__ import annotations

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSource,
    CaptureSourceKind,
    FeedCaptureIntent,
    FeedFrameContext,
    FeedSelection,
    NormalizedPoint,
    OwnershipState,
)
from stylecapture_backend.features.look.application import (
    LookApplication,
    LookNotFoundError,
)
from stylecapture_backend.features.look.domain import (
    Look,
    LookComponent,
    LookDetail,
    PreferenceSignal,
)


class MemoryLookRepository:
    def __init__(self) -> None:
        self.looks: dict[tuple[UUID, str], Look] = {}
        self.preferences: dict[tuple[UUID, str], PreferenceSignal] = {}

    async def ensure_placeholder(
        self,
        look: Look,
        signal: PreferenceSignal,
    ) -> Look:
        identity = (look.capture_id, look.source_selection_key)
        stored = self.looks.setdefault(identity, look)
        preference_identity = (signal.user_id, signal.idempotency_key)
        self.preferences.setdefault(
            preference_identity,
            replace(signal, look_id=stored.id),
        )
        return stored

    async def get_by_capture(
        self,
        capture_id: UUID,
        source_selection_key: str,
    ) -> Look | None:
        return self.looks.get((capture_id, source_selection_key))

    async def list_for_user(self, user_id: UUID) -> list[Look]:
        return [look for look in self.looks.values() if look.user_id == user_id]

    async def get_detail_for_user(
        self,
        look_id: UUID,
        user_id: UUID,
    ) -> LookDetail | None:
        look = next(
            (
                candidate
                for candidate in self.looks.values()
                if candidate.id == look_id and candidate.user_id == user_id
            ),
            None,
        )
        if look is None:
            return None
        preferences = tuple(
            signal
            for signal in self.preferences.values()
            if signal.look_id == look.id and signal.user_id == user_id
        )
        return LookDetail(look=look, components=(), preference_signals=preferences)

    async def append_preference(
        self,
        signal: PreferenceSignal,
    ) -> PreferenceSignal:
        return self.preferences.setdefault(
            (signal.user_id, signal.idempotency_key),
            signal,
        )

    async def save(self, look: Look) -> Look:
        self.looks[(look.capture_id, look.source_selection_key)] = look
        return look

    async def save_component(self, component: LookComponent) -> LookComponent:
        return component


def whole_outfit_capture(*, user_id: UUID) -> Capture:
    context = FeedFrameContext(
        video_ref="feed://look-1",
        timestamp_ms=2_400,
        frame_width=720,
        frame_height=1280,
        selections=(
            FeedSelection(
                selection_key="whole-look",
                polygon=(
                    NormalizedPoint(0.1, 0.1),
                    NormalizedPoint(0.8, 0.1),
                    NormalizedPoint(0.8, 0.9),
                ),
            ),
        ),
        intent=FeedCaptureIntent.WHOLE_OUTFIT,
    )
    return Capture.create(
        user_id=user_id,
        source=CaptureSource(
            kind=CaptureSourceKind.FEED,
            object_key="originals/feed/look.png",
            sha256="a" * 64,
            origin_ref=context.video_ref,
        ),
        ownership=OwnershipState.INSPIRATION,
        feed_context=context,
    )


@pytest.mark.asyncio
async def test_ensure_saved_look_is_idempotent_with_one_append_only_save_signal() -> None:
    user_id = uuid4()
    capture = whole_outfit_capture(user_id=user_id)
    repository = MemoryLookRepository()
    application = LookApplication(looks=repository)

    first = await application.ensure_saved_look(
        capture,
        idempotency_key="feed-save-request",
    )
    second = await application.ensure_saved_look(
        capture,
        idempotency_key="feed-save-request",
    )

    assert second == first
    assert list(repository.looks.values()) == [first]
    assert len(repository.preferences) == 1
    signal = next(iter(repository.preferences.values()))
    assert signal.look_id == first.id
    assert signal.user_id == user_id


@pytest.mark.asyncio
async def test_list_detail_and_liking_reason_are_user_scoped_and_idempotent() -> None:
    owner_id = uuid4()
    other_user_id = uuid4()
    repository = MemoryLookRepository()
    application = LookApplication(looks=repository)
    look = await application.ensure_saved_look(
        whole_outfit_capture(user_id=owner_id),
        idempotency_key="save-look",
    )

    listed = await application.list_looks(user_id=owner_id)
    detail = await application.get_look(user_id=owner_id, look_id=look.id)
    first_reason = await application.record_liking_reason(
        user_id=owner_id,
        look_id=look.id,
        reason="喜欢层次感",
        idempotency_key="reason-request",
    )
    second_reason = await application.record_liking_reason(
        user_id=owner_id,
        look_id=look.id,
        reason="喜欢层次感",
        idempotency_key="reason-request",
    )

    assert listed == [look]
    assert detail.look == look
    assert first_reason == second_reason
    assert len(repository.preferences) == 2
    with pytest.raises(LookNotFoundError):
        await application.get_look(user_id=other_user_id, look_id=look.id)
    with pytest.raises(LookNotFoundError):
        await application.record_liking_reason(
            user_id=other_user_id,
            look_id=look.id,
            reason="不应写入",
            idempotency_key="cross-user-reason",
        )
