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
BORDER_INSET = 0.055
BACKDROP_TOLERANCE = 34
SPARKLE_MINIMUM_CHANNEL = 232
SUPPORT_SURFACE_TOP = 0.66
SUPPORT_SURFACE_SIDE_WIDTH = 0.22
SUPPORT_SURFACE_SPREAD_TOLERANCE = 40
MIN_SUBJECT_RATIO = 0.015
MAX_SUBJECT_RATIO = 0.82


class PillowPixelSpriteExtractor:
    """Extract the central pixel character from a generated illustration card.

    Pixel cards use a small palette of broad background regions and a blocky subject
    with comparatively sharp edges. Flooding sampled outer and inner backdrop colours
    removes the card without loading a general-purpose matting model. A lower-gutter
    pass removes rugs touching the shoes, then largest-component filtering removes
    frames, sparkles, and disconnected decorations.
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
        backdrop = _flood_backdrop(working)
        subject = bytearray(0 if value else 1 for value in backdrop)
        _remove_support_surface(subject, pixels, width, height)
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


def _median_color(samples: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    channels = tuple(
        sorted(sample[channel] for sample in samples)[len(samples) // 2] for channel in range(3)
    )
    return cast(tuple[int, int, int], channels)


def _distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return sum(abs(left[channel] - right[channel]) for channel in range(3))


def _rgb_at(pixels: Any, x: int, y: int) -> tuple[int, int, int]:
    value = pixels[x, y]
    return (int(value[0]), int(value[1]), int(value[2]))


def _backdrop_palette(
    image: Image.Image,
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int]]]:
    pixels = cast(Any, image.load())
    width, height = image.size
    inset = max(1, int(min(width, height) * BORDER_INSET))

    border: list[tuple[int, int, int]] = []
    for x in range(inset, width - inset, 4):
        border.append(_rgb_at(pixels, x, inset))
        border.append(_rgb_at(pixels, x, height - inset - 1))
    for y in range(inset, height - inset, 4):
        border.append(_rgb_at(pixels, inset, y))
        border.append(_rgb_at(pixels, width - inset - 1, y))

    probes = [
        (round(width * fraction_x), round(height * fraction_y))
        for fraction_x in (0.15, 0.85)
        for fraction_y in (0.25, 0.5, 0.75)
    ]
    probe_colors = [_rgb_at(pixels, x, y) for x, y in probes]
    interior = _median_color(probe_colors)
    seeds = [
        point
        for point, color in zip(probes, probe_colors, strict=False)
        if _distance(color, interior) <= BACKDROP_TOLERANCE
    ]
    return [_median_color(border), interior], seeds


def _is_backdrop(
    pixel: tuple[int, int, int],
    palette: list[tuple[int, int, int]],
) -> bool:
    if any(_distance(pixel, backdrop) <= BACKDROP_TOLERANCE for backdrop in palette):
        return True
    return min(pixel) >= SPARKLE_MINIMUM_CHANNEL


def _flood_backdrop(image: Image.Image) -> bytearray:
    pixels = cast(Any, image.load())
    width, height = image.size
    palette, interior_seeds = _backdrop_palette(image)
    backdrop = bytearray(width * height)
    queue: deque[int] = deque()

    def visit(x: int, y: int) -> None:
        index = y * width + x
        if backdrop[index]:
            return
        if not _is_backdrop(_rgb_at(pixels, x, y), palette):
            return
        backdrop[index] = 1
        queue.append(index)

    for x in range(width):
        visit(x, 0)
        visit(x, height - 1)
    for y in range(1, height - 1):
        visit(0, y)
        visit(width - 1, y)
    for x, y in interior_seeds:
        visit(x, y)

    while queue:
        index = queue.popleft()
        x = index % width
        y = index // width
        if x > 0:
            visit(x - 1, y)
        if x < width - 1:
            visit(x + 1, y)
        if y > 0:
            visit(x, y - 1)
        if y < height - 1:
            visit(x, y + 1)
    return backdrop


def _remove_support_surface(mask: bytearray, pixels: Any, width: int, height: int) -> None:
    """Remove a wide illustrated rug or platform touching the character's shoes.

    Generated cards often place the person on a carpet. The carpet can touch the
    shoes, so largest-component filtering alone keeps both. At the bottom of a
    portrait card the person's body stays central while the carpet reaches both
    side gutters; flooding only those lower side-connected colours removes the
    support without crossing the high-contrast shoe outline.
    """

    top = round(height * SUPPORT_SURFACE_TOP)
    side = max(1, round(width * SUPPORT_SURFACE_SIDE_WIDTH))
    support = bytearray(width * height)
    queue: deque[int] = deque()

    def seed(index: int) -> None:
        if not mask[index] or support[index]:
            return
        support[index] = 1
        queue.append(index)

    for y in range(top, height):
        row = y * width
        for x in range(side):
            seed(row + x)
            seed(row + width - x - 1)

    while queue:
        index = queue.popleft()
        x = index % width
        y = index // width
        current = _rgb_at(pixels, x, y)
        neighbours = []
        if x > 0:
            neighbours.append(index - 1)
        if x < width - 1:
            neighbours.append(index + 1)
        if y > top:
            neighbours.append(index - width)
        if y < height - 1:
            neighbours.append(index + width)
        for neighbour in neighbours:
            if not mask[neighbour] or support[neighbour]:
                continue
            next_x = neighbour % width
            next_y = neighbour // width
            candidate = _rgb_at(pixels, next_x, next_y)
            if _distance(current, candidate) <= SUPPORT_SURFACE_SPREAD_TOLERANCE:
                support[neighbour] = 1
                queue.append(neighbour)

    for index, remove in enumerate(support):
        if remove:
            mask[index] = 0


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
