from __future__ import annotations

from hashlib import sha256
from io import BytesIO

from PIL import Image
from pillow_heif import register_heif_opener

from stylecapture_backend.platform.image_payload import ImagePayload

PROVIDER_SAFE_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
HEIF_IMAGE_TYPES = frozenset({"image/heic", "image/heif"})


def normalize_provider_image(
    image: ImagePayload,
    *,
    max_edge: int = 2048,
    quality: int = 90,
) -> ImagePayload:
    """Return provider/browser-safe bytes while leaving the stored original untouched."""

    content_type = image.content_type.lower()
    if content_type in PROVIDER_SAFE_IMAGE_TYPES:
        return image
    if content_type not in HEIF_IMAGE_TYPES:
        return image

    register_heif_opener()
    with Image.open(BytesIO(image.body)) as source:
        rendered = source.convert("RGB")
        rendered.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        rendered.save(buffer, format="JPEG", quality=quality, optimize=True)
    body = buffer.getvalue()
    return ImagePayload(
        object_key=f"{image.object_key}.render-input.jpg",
        content_type="image/jpeg",
        body=body,
        sha256=sha256(body).hexdigest(),
    )


def optimize_browser_image(
    image: ImagePayload,
    *,
    minimum_bytes: int = 256 * 1024,
    max_edge: int = 1600,
    quality: int = 88,
) -> ImagePayload:
    """Serve large transparent PNGs as compact, browser-safe WebP images.

    The stored PNG remains the canonical derived garment. This presentation
    transform keeps its alpha channel while avoiding multi-megabyte responses
    on constrained mobile networks.
    """

    if image.content_type.lower() != "image/png" or len(image.body) < minimum_bytes:
        return image

    with Image.open(BytesIO(image.body)) as source:
        rendered = source.convert("RGBA") if source.mode != "RGBA" else source.copy()
        rendered.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        rendered.save(buffer, format="WEBP", quality=quality, method=4)
    body = buffer.getvalue()
    if len(body) >= len(image.body):
        return image
    return ImagePayload(
        object_key=f"{image.object_key}.browser.webp",
        content_type="image/webp",
        body=body,
        sha256=sha256(body).hexdigest(),
    )
