from __future__ import annotations

from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageDraw
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.render.infrastructure.pixel_sprite_cutout import (
    PillowPixelSpriteExtractor,
)


def test_pixel_sprite_extractor_removes_card_and_keeps_character() -> None:
    source = _pixel_card()

    result = PillowPixelSpriteExtractor().extract(source)

    assert result.content_type == "image/png"
    assert result.sha256 == sha256(result.body).hexdigest()
    with Image.open(BytesIO(result.body)) as image:
        rgba = image.convert("RGBA")
        assert rgba.height <= 360
        assert rgba.width < rgba.height
        alpha = rgba.getchannel("A")
        assert alpha.getpixel((0, 0)) == 0
        assert alpha.getbbox() is not None
        opaque = sum(alpha.histogram()[1:])
        assert opaque / (rgba.width * rgba.height) > 0.35
        pixels = rgba.load()
        assert pixels is not None
        center = pixels[rgba.width // 2, rgba.height // 2]
        assert isinstance(center, tuple)
        assert center[3] == 255


def test_pixel_sprite_extractor_removes_carpet_touching_the_shoes() -> None:
    result = PillowPixelSpriteExtractor().extract(_pixel_card(with_carpet=True))

    with Image.open(BytesIO(result.body)) as image:
        rgba = image.convert("RGBA")
        # The character is roughly 100 px wide in the source. Keeping the
        # 200 px carpet would make the trimmed sprite almost card-width.
        assert rgba.width < 140
        alpha = rgba.getchannel("A")
        assert alpha.getpixel((0, rgba.height - 1)) == 0
        assert alpha.getpixel((rgba.width - 1, rgba.height - 1)) == 0


def _pixel_card(*, with_carpet: bool = False) -> ImagePayload:
    width, height = 240, 320
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    assert pixels is not None
    for y in range(height):
        for x in range(width):
            pixels[x, y] = (
                240 - y // 16,
                228 - x // 24,
                250 - y // 20,
            )

    draw = ImageDraw.Draw(image)
    # Disconnected card decorations must not survive as part of the sprite.
    draw.rectangle((15, 20, 24, 29), fill=(255, 180, 220))
    draw.rectangle((210, 50, 217, 57), fill=(180, 220, 255))
    if with_carpet:
        draw.ellipse((20, 268, 220, 314), fill=(235, 184, 116), outline=(185, 128, 72), width=4)
        draw.ellipse((45, 278, 195, 304), outline=(255, 238, 202), width=5)
    # One connected, deliberately blocky character.
    draw.rectangle((92, 42, 147, 90), fill=(70, 42, 35))
    draw.rectangle((82, 88, 157, 205), fill=(195, 62, 96))
    draw.rectangle((68, 96, 91, 176), fill=(232, 170, 135))
    draw.rectangle((148, 96, 171, 176), fill=(232, 170, 135))
    draw.rectangle((88, 201, 117, 278), fill=(70, 130, 205))
    draw.rectangle((122, 201, 151, 278), fill=(70, 130, 205))
    draw.rectangle((80, 276, 117, 292), fill=(40, 42, 50))
    draw.rectangle((122, 276, 159, 292), fill=(40, 42, 50))

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    body = buffer.getvalue()
    return ImagePayload(
        object_key="derived/pixel-trials/test/card.png",
        content_type="image/png",
        body=body,
        sha256=sha256(body).hexdigest(),
    )
