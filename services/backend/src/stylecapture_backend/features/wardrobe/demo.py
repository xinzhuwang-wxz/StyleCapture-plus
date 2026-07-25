from __future__ import annotations

from typing import Protocol
from uuid import UUID


class DemoWardrobeBootstrapper(Protocol):
    async def ensure_for_user(self, user_id: UUID) -> None: ...
