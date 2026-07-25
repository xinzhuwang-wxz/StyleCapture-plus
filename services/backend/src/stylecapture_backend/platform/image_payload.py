from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImagePayload:
    """Provider-neutral image bytes shared across product capabilities."""

    object_key: str
    content_type: str
    body: bytes
    sha256: str

    def __post_init__(self) -> None:
        if not self.body:
            raise ValueError("image body must not be empty")
        if not self.content_type.startswith("image/"):
            raise ValueError("content_type must describe an image")
