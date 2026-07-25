from __future__ import annotations

import pytest
from stylecapture_backend.features.capture.domain import (
    FeedCaptureIntent,
    FeedFrameContext,
    FeedSelection,
    NormalizedPoint,
)


def _selection(key: str) -> FeedSelection:
    return FeedSelection(
        selection_key=key,
        polygon=(
            NormalizedPoint(0.1, 0.1),
            NormalizedPoint(0.9, 0.1),
            NormalizedPoint(0.9, 0.9),
        ),
    )


def test_item_selection_intent_accepts_multiple_lassos() -> None:
    context = FeedFrameContext(
        video_ref="feed-look-001",
        timestamp_ms=1_250,
        frame_width=390,
        frame_height=844,
        selections=(_selection("top"), _selection("bottom")),
    )

    assert context.intent is FeedCaptureIntent.ITEM_SELECTIONS


def test_whole_outfit_intent_requires_exactly_one_lasso() -> None:
    with pytest.raises(
        ValueError,
        match="whole-outfit Feed capture must contain exactly one selection",
    ):
        FeedFrameContext(
            video_ref="feed-look-001",
            timestamp_ms=1_250,
            frame_width=390,
            frame_height=844,
            selections=(_selection("top"), _selection("bottom")),
            intent=FeedCaptureIntent.WHOLE_OUTFIT,
        )
