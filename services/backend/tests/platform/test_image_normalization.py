from __future__ import annotations

from hashlib import sha256
from io import BytesIO

from PIL import Image
from stylecapture_backend.platform.image_normalization import optimize_browser_image
from stylecapture_backend.platform.image_payload import ImagePayload


def test_large_transparent_png_is_compacted_for_browser_delivery() -> None:
    source = Image.effect_noise((900, 900), 80).convert("RGBA")
    source.putalpha(Image.new("L", source.size, 220))
    source.putpixel((0, 0), (255, 255, 255, 0))
    buffer = BytesIO()
    source.save(buffer, format="PNG")
    body = buffer.getvalue()
    payload = ImagePayload(
        object_key="derived/items/example.png",
        content_type="image/png",
        body=body,
        sha256=sha256(body).hexdigest(),
    )

    optimized = optimize_browser_image(payload, minimum_bytes=1)

    assert optimized.content_type == "image/webp"
    assert len(optimized.body) < len(payload.body)
    with Image.open(BytesIO(optimized.body)) as rendered:
        assert rendered.mode == "RGBA"
        pixel = rendered.getpixel((0, 0))
        assert isinstance(pixel, tuple)
        assert len(pixel) == 4
        assert pixel[3] == 0


def test_small_png_is_returned_without_reencoding() -> None:
    body = b"small-png-placeholder"
    payload = ImagePayload(
        object_key="derived/items/example.png",
        content_type="image/png",
        body=body,
        sha256=sha256(body).hexdigest(),
    )

    assert optimize_browser_image(payload) is payload
