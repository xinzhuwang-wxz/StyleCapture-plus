from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image

from stylecapture_backend.features.capture.domain import ImagePayload


def image_to_jpeg_data_url(
    image: ImagePayload,
    *,
    max_edge: int = 2048,
    quality: int = 90,
) -> str:
    with Image.open(BytesIO(image.body)) as source:
        rendered = source.convert("RGB")
        rendered.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        rendered.save(buffer, format="JPEG", quality=quality, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
