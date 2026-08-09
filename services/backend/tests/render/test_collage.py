from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from typing import cast

import pytest
from PIL import Image
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.render.infrastructure.collage import (
    CollageRenderError,
    PillowLookCollageRenderer,
)


def payload(
    name: str, color: tuple[int, int, int], size: tuple[int, int] = (80, 120)
) -> ImagePayload:
    buffer = BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    body = buffer.getvalue()
    return ImagePayload(
        object_key=f"derived/items/{name}.png",
        content_type="image/png",
        body=body,
        sha256=sha256(body).hexdigest(),
    )


def decode(body: bytes) -> Image.Image:
    with Image.open(BytesIO(body)) as image:
        return image.copy()


def pixel_rgba(image: Image.Image, xy: tuple[int, int]) -> tuple[int, int, int, int]:
    return cast(tuple[int, int, int, int], image.getpixel(xy))


def test_collage_defaults_to_a_stable_pure_white_portrait_png() -> None:
    images = [
        payload("top", (255, 0, 64)),
        payload("bottom", (40, 120, 255)),
        payload("bag", (255, 210, 40)),
        payload("shoe", (40, 210, 120)),
        payload("hat", (180, 80, 255)),
        payload("coat", (80, 60, 50)),
    ]
    renderer = PillowLookCollageRenderer()

    output = renderer.render(images)
    repeated = renderer.render(images)
    image = decode(output.body).convert("RGBA")

    assert output.content_type == "image/png"
    assert output.object_key == "derived/renders/collage-pending.png"
    assert output.sha256 == sha256(output.body).hexdigest()
    assert output.body == repeated.body
    assert image.size == (768, 1024)
    assert pixel_rgba(image, (0, 0)) == (255, 255, 255, 255)


def test_collage_transparent_background_is_explicit() -> None:
    output = PillowLookCollageRenderer(
        canvas_width=320,
        canvas_height=426,
        padding=24,
        transparent_background=True,
    ).render([payload("dress", (255, 120, 180), size=(90, 160))])

    image = decode(output.body).convert("RGBA")

    assert pixel_rgba(image, (0, 0))[3] == 0


def test_collage_balances_primary_items_and_a_right_hand_rail() -> None:
    first = payload("first", (250, 0, 0), size=(80, 80))
    second = payload("second", (0, 0, 250), size=(80, 80))
    third = payload("third", (0, 200, 80), size=(80, 80))
    renderer = PillowLookCollageRenderer(
        canvas_width=320,
        canvas_height=426,
        padding=20,
        gap=12,
    )

    image = decode(renderer.render([first, second, third]).body).convert("RGBA")

    assert pixel_rgba(image, (95, 100))[:3] == (250, 0, 0)
    assert pixel_rgba(image, (95, 300))[:3] == (0, 0, 250)
    assert pixel_rgba(image, (240, 213))[:3] == (0, 200, 80)


def test_collage_rejects_empty_or_too_many_inputs() -> None:
    renderer = PillowLookCollageRenderer()

    with pytest.raises(CollageRenderError, match="at least one"):
        renderer.render([])

    with pytest.raises(CollageRenderError, match="at most eight"):
        renderer.render([payload(str(index), (index, index, index)) for index in range(9)])
