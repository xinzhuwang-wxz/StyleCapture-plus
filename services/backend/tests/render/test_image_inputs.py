from __future__ import annotations

from hashlib import sha256
from io import BytesIO

from PIL import Image
from pillow_heif import from_pillow
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.platform.image_normalization import normalize_provider_image


def test_normalize_render_image_converts_real_heic_bytes_to_jpeg() -> None:
    source = heic_payload()

    normalized = normalize_provider_image(source)

    assert normalized.content_type == "image/jpeg"
    assert normalized.object_key.endswith(".render-input.jpg")
    assert normalized.sha256 == sha256(normalized.body).hexdigest()
    with Image.open(BytesIO(normalized.body)) as image:
        assert image.format == "JPEG"
        assert image.size == (8, 6)


def test_normalize_render_image_keeps_png_jpeg_and_webp_bytes_unchanged() -> None:
    for content_type in ("image/png", "image/jpeg", "image/webp"):
        source = ImagePayload(
            object_key=f"derived/input.{content_type.split('/')[-1]}",
            content_type=content_type,
            body=b"already-safe",
            sha256=sha256(b"already-safe").hexdigest(),
        )

        assert normalize_provider_image(source) is source


def heic_payload() -> ImagePayload:
    image = Image.new("RGB", (8, 6), (25, 90, 180))
    heif = from_pillow(image)
    buffer = BytesIO()
    heif.save(buffer, format="HEIF")
    body = buffer.getvalue()
    return ImagePayload(
        object_key="originals/upload/phone-photo.heic",
        content_type="image/heic",
        body=body,
        sha256=sha256(body).hexdigest(),
    )
