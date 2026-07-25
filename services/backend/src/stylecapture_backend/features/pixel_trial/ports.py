from __future__ import annotations

from typing import Protocol
from uuid import UUID

from stylecapture_backend.features.pixel_trial.domain import PixelTrial

PIXEL_TRIAL_TASK_NAME = "stylecapture.pixel_trial.process"


class PixelTrialNotFound(LookupError):
    """The requested pixel trial is not visible to the current user."""


class PixelTrialIdempotencyConflict(ValueError):
    """A pixel trial request key was reused for different input."""


class PixelTrialPersistenceUnavailable(RuntimeError):
    """The pixel trial store is temporarily unavailable for a safe retry."""


class PixelTrialRepository(Protocol):
    async def ensure_requested(self, trial: PixelTrial) -> PixelTrial: ...

    async def save(self, trial: PixelTrial) -> PixelTrial: ...

    async def get_for_user(self, *, user_id: UUID, trial_id: UUID) -> PixelTrial | None: ...

    async def delete_for_user(self, *, user_id: UUID, trial_id: UUID) -> PixelTrial | None: ...
