from __future__ import annotations

from collections import deque
from hashlib import sha256
from io import BytesIO
from typing import Any, cast

from PIL import Image, UnidentifiedImageError
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.pixel_trial.ports import PixelSpriteExtractionError

SEGMENTATION_MAX_HEIGHT = 720
SPRITE_MAX_HEIGHT = 360
MAX_SOURCE_PIXELS = 36_000_000
EDGE_PADDING = 4
BACKDROP_SPREAD_TOLERANCE = 26
MIN_SUBJECT_RATIO = 0.015
MAX_SUBJECT_RATIO = 0.82


class PillowPixelSpriteExtractor:
    """Extract the central pixel character from a generated illustration card.

    Pixel cards use broad, slowly varying background regions and a blocky subject
    with comparatively sharp edges. Flooding locally similar pixels from the card
    edges and side gutters removes those regions without loading a general-purpose
    matting model. Keeping the largest remaining component removes frames, sparkles,
    and disconnected decorations.
    """

    def extract(self, image: ImagePayload) -> ImagePayload:
        try:
            with Image.open(BytesIO(image.body)) as opened:
                if (
                    opened.width <= 0
                    or opened.height <= 0
                    or opened.width * opened.height > MAX_SOURCE_PIXELS
                ):
                    raise PixelSpriteExtractionError(
                        "generated pixel card dimensions exceed the safe limit"
                    )
                source = opened.convert("RGBA")
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as error:
            raise PixelSpriteExtractionError("generated pixel card is not a valid image") from error

        working = _fit_for_segmentation(source)
        width, height = working.size
        pixels = cast(Any, working.load())
        backdrop = _flood_backdrop(pixels, width, height)
        subject = bytearray(0 if value else 1 for value in backdrop)
        subject = _largest_component(subject, width, height)

        kept = sum(subject)
        ratio = kept / (width * height)
        if kept == 0 or not MIN_SUBJECT_RATIO <= ratio <= MAX_SUBJECT_RATIO:
            raise PixelSpriteExtractionError("pixel card character mask failed quality checks")

        result = working.copy()
        result_pixels = cast(Any, result.load())
        min_x, min_y, max_x, max_y = width, height, -1, -1
        for index, keep in enumerate(subject):
            x = index % width
            y = index // width
            red, green, blue, _ = result_pixels[x, y]
            if keep:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
                result_pixels[x, y] = (red, green, blue, 255)
            else:
                result_pixels[x, y] = (red, green, blue, 0)

        if max_x < min_x or max_y < min_y:
            raise PixelSpriteExtractionError("pixel card character mask is empty")
        box = (
            max(0, min_x - EDGE_PADDING),
            max(0, min_y - EDGE_PADDING),
            min(width, max_x + EDGE_PADDING + 1),
            min(height, max_y + EDGE_PADDING + 1),
        )
        sprite = result.crop(box)
        if sprite.height > SPRITE_MAX_HEIGHT:
            scale = SPRITE_MAX_HEIGHT / sprite.height
            sprite = sprite.resize(
                (max(1, round(sprite.width * scale)), SPRITE_MAX_HEIGHT),
                Image.Resampling.NEAREST,
            )

        output = BytesIO()
        sprite.save(output, format="PNG", optimize=True)
        body = output.getvalue()
        return ImagePayload(
            object_key=f"{image.object_key}.sprite.png",
            content_type="image/png",
            body=body,
            sha256=sha256(body).hexdigest(),
        )


def _fit_for_segmentation(image: Image.Image) -> Image.Image:
    if image.height <= SEGMENTATION_MAX_HEIGHT:
        return image.copy()
    scale = SEGMENTATION_MAX_HEIGHT / image.height
    return image.resize(
        (max(1, round(image.width * scale)), SEGMENTATION_MAX_HEIGHT),
        Image.Resampling.NEAREST,
    )


def _flood_backdrop(pixels: Any, width: int, height: int) -> bytearray:
    backdrop = bytearray(width * height)
    queue: deque[int] = deque()

    def seed(x: int, y: int) -> None:
        index = y * width + x
        if backdrop[index]:
            return
        backdrop[index] = 1
        queue.append(index)

    for x in range(width):
        seed(x, 0)
        seed(x, height - 1)
    for y in range(1, height - 1):
        seed(0, y)
        seed(width - 1, y)

    # Decorative borders can isolate the inner card background from the canvas
    # edge. Generated characters are centered, so narrow side gutters are safe
    # additional seeds and mirror the existing offline cutout script.
    gutter_columns = {
        max(0, min(width - 1, round(width * fraction))) for fraction in (0.06, 0.12, 0.88, 0.94)
    }
    gutter_step = max(1, height // 24)
    for x in gutter_columns:
        for y in range(gutter_step, height - gutter_step, gutter_step):
            seed(x, y)

    while queue:
        index = queue.popleft()
        x = index % width
        y = index // width
        current = pixels[x, y]
        neighbours: tuple[tuple[int, int], ...] = (
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
        )
        for next_x, next_y in neighbours:
            if next_x < 0 or next_x >= width or next_y < 0 or next_y >= height:
                continue
            next_index = next_y * width + next_x
            if backdrop[next_index]:
                continue
            candidate = pixels[next_x, next_y]
            if _locally_similar(current, candidate):
                backdrop[next_index] = 1
                queue.append(next_index)
    return backdrop


def _locally_similar(left: Any, right: Any) -> bool:
    return max(abs(int(left[channel]) - int(right[channel])) for channel in range(3)) <= (
        BACKDROP_SPREAD_TOLERANCE
    )


def _largest_component(mask: bytearray, width: int, height: int) -> bytearray:
    visited = bytearray(width * height)
    largest: list[int] = []
    for start, opaque in enumerate(mask):
        if not opaque or visited[start]:
            continue
        component: list[int] = []
        queue: deque[int] = deque([start])
        visited[start] = 1
        while queue:
            index = queue.popleft()
            component.append(index)
            x = index % width
            y = index // width
            neighbours = []
            if x > 0:
                neighbours.append(index - 1)
            if x < width - 1:
                neighbours.append(index + 1)
            if y > 0:
                neighbours.append(index - width)
            if y < height - 1:
                neighbours.append(index + width)
            for neighbour in neighbours:
                if mask[neighbour] and not visited[neighbour]:
                    visited[neighbour] = 1
                    queue.append(neighbour)
        if len(component) > len(largest):
            largest = component

    kept = bytearray(width * height)
    for index in largest:
        kept[index] = 1
    return kept
