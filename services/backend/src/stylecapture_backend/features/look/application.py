from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureSourceKind,
    FeedCaptureIntent,
)
from stylecapture_backend.features.look.domain import Look, LookDetail, PreferenceSignal
from stylecapture_backend.features.look.ports import LookRepository


class InvalidLookCapture(ValueError):
    """The capture does not represent one explicitly selected whole outfit."""


class LookNotFoundError(LookupError):
    """The requested Look is not visible to the current user."""


class LookApplication:
    def __init__(self, *, looks: LookRepository) -> None:
        self._looks = looks

    async def ensure_saved_look(
        self,
        capture: Capture,
        *,
        idempotency_key: str,
    ) -> Look:
        feed_context = capture.feed_context
        if (
            capture.source.kind is not CaptureSourceKind.FEED
            or feed_context is None
            or feed_context.intent is not FeedCaptureIntent.WHOLE_OUTFIT
            or len(feed_context.selections) != 1
        ):
            raise InvalidLookCapture(
                "saved Look registration requires one whole-outfit Feed selection"
            )

        request_key = idempotency_key.strip()
        if not request_key:
            raise ValueError("idempotency key must not be empty")
        selection = feed_context.selections[0]
        look = Look.feed_saved(
            user_id=capture.user_id,
            capture_id=capture.id,
            source_selection_key=selection.selection_key,
        )
        signal = PreferenceSignal.look_saved(
            user_id=capture.user_id,
            look_id=look.id,
            idempotency_key=f"capture-save:{sha256(request_key.encode()).hexdigest()}",
        )
        return await self._looks.ensure_placeholder(look, signal)

    async def list_looks(self, *, user_id: UUID) -> list[Look]:
        return await self._looks.list_for_user(user_id)

    async def get_look(self, *, user_id: UUID, look_id: UUID) -> LookDetail:
        detail = await self._looks.get_detail_for_user(look_id, user_id)
        if detail is None:
            raise LookNotFoundError("Look not found")
        return detail

    async def record_liking_reason(
        self,
        *,
        user_id: UUID,
        look_id: UUID,
        reason: str,
        idempotency_key: str,
    ) -> PreferenceSignal:
        if await self._looks.get_detail_for_user(look_id, user_id) is None:
            raise LookNotFoundError("Look not found")
        signal = PreferenceSignal.liking_reason(
            user_id=user_id,
            look_id=look_id,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        return await self._looks.append_preference(signal)
