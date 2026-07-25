from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from stylecapture_backend.features.capture.domain import (
    Capture,
    CaptureIntent,
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
        feed_outfit = (
            capture.source.kind is CaptureSourceKind.FEED
            and feed_context is not None
            and feed_context.intent is FeedCaptureIntent.WHOLE_OUTFIT
            and len(feed_context.selections) == 1
        )
        uploaded_outfit = (
            capture.source.kind in {CaptureSourceKind.UPLOAD, CaptureSourceKind.CAMERA}
            and capture.intent is CaptureIntent.WHOLE_OUTFIT
        )
        if not feed_outfit and not uploaded_outfit:
            raise InvalidLookCapture(
                "saved Look registration requires an explicit whole-outfit capture"
            )

        request_key = idempotency_key.strip()
        if not request_key:
            raise ValueError("idempotency key must not be empty")
        source_selection_key = (
            feed_context.selections[0].selection_key
            if feed_outfit and feed_context is not None
            else "whole_outfit"
        )
        look = (
            Look.feed_saved(
                user_id=capture.user_id,
                capture_id=capture.id,
                source_selection_key=source_selection_key,
            )
            if feed_outfit
            else Look.user_created(
                user_id=capture.user_id,
                capture_id=capture.id,
                source_selection_key=source_selection_key,
            )
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
