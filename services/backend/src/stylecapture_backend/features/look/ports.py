from __future__ import annotations

from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.look.domain import (
    Look,
    LookComponent,
    LookDeletionResult,
    LookDetail,
    PreferenceSignal,
)


class LookItemOwnershipMismatch(ValueError):
    """A Look component attempted to reference another user's Item."""


class PreferenceIdempotencyConflict(ValueError):
    """One preference idempotency key was reused for different semantics."""


class LookPersistenceUnavailable(RuntimeError):
    """The Look store is temporarily unavailable for a safe retry."""


class LookRepository(Protocol):
    async def save_bundle(
        self,
        look: Look,
        components: tuple[LookComponent, ...],
        signal: PreferenceSignal,
    ) -> Look: ...

    async def ensure_placeholder(
        self,
        look: Look,
        signal: PreferenceSignal,
    ) -> Look: ...

    async def get_by_capture(
        self,
        capture_id: UUID,
        source_selection_key: str,
    ) -> Look | None: ...

    async def list_for_user(self, user_id: UUID) -> list[Look]: ...

    async def get_detail_for_user(
        self,
        look_id: UUID,
        user_id: UUID,
    ) -> LookDetail | None: ...

    async def append_preference(
        self,
        signal: PreferenceSignal,
    ) -> PreferenceSignal: ...

    async def save(self, look: Look) -> Look: ...

    async def save_component(self, component: LookComponent) -> LookComponent: ...

    async def delete_for_user(
        self,
        look_id: UUID,
        user_id: UUID,
        *,
        delete_items: bool,
    ) -> LookDeletionResult | None: ...
