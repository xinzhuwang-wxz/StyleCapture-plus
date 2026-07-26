"""Cut bundled Style Party portraits into clean transparent character sprites.

The supplied pixel Looks are 1086x1448 illustration cards: a decorative frame, a
pale backdrop with sparkles, and the character in the middle. The party world
needs the character alone, small enough to load several at once.

Run offline whenever the source portraits change:

    uv run python scripts/pixel_look_cutout.py

The runtime keeps its own cutout path for user uploads; this script only
pre-processes the assets that ship with the repository.
"""

from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMUNITY_ASSETS = REPO_ROOT / "apps/h5/public/assets/community"
OUTPUT_DIR = COMMUNITY_ASSETS / "cutouts"

# The illustration frame hugs the edge; ignore it before sampling the backdrop.
BORDER_INSET = 0.055
# Colour distance under which a pixel counts as the same flat backdrop.
BACKDROP_TOLERANCE = 34
# Sparkles sit on the backdrop and are lighter than every inked character pixel.
SPARKLE_MINIMUM_CHANNEL = 232
TARGET_HEIGHT = 360
EDGE_PADDING = 4


@dataclass(frozen=True)
class Cutout:
    source: Path
    destination: Path


def _median_color(
    samples: list[tuple[int, int, int]],
) -> tuple[int, int, int]:
    channels = tuple(
        sorted(sample[channel] for sample in samples)[len(samples) // 2]
        for channel in range(3)
    )
    return channels  # type: ignore[return-value]


def _distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return sum(abs(left[channel] - right[channel]) for channel in range(3))


def _backdrop_palette(
    image: Image.Image, inset: int
) -> tuple[list[tuple[int, int, int]], list[tuple[int, int]]]:
    """Backdrop colours plus interior seed points.

    A card can have two flat areas: the paper outside the decorative frame and
    the illustration backdrop inside it. Border sampling only ever finds the
    outer one, so the flood would stop at the frame. Probing columns to the left
    and right of the subject recovers the inner backdrop and gives the flood a
    seed inside the frame.
    """
    pixels = image.load()
    width, height = image.size

    border: list[tuple[int, int, int]] = []
    for x in range(inset, width - inset, 4):
        border.append(pixels[x, inset][:3])
        border.append(pixels[x, height - inset - 1][:3])
    for y in range(inset, height - inset, 4):
        border.append(pixels[inset, y][:3])
        border.append(pixels[width - inset - 1, y][:3])

    # Characters occupy the middle of the card, so these columns stay clear.
    probes = [
        (round(width * fraction_x), round(height * fraction_y))
        for fraction_x in (0.15, 0.85)
        for fraction_y in (0.25, 0.5, 0.75)
    ]
    probe_colors = [pixels[x, y][:3] for x, y in probes]
    interior = _median_color(probe_colors)
    # Drop any probe that landed on artwork rather than the flat backdrop.
    seeds = [
        point
        for point, color in zip(probes, probe_colors)
        if _distance(color, interior) <= BACKDROP_TOLERANCE
    ]

    return [_median_color(border), interior], seeds


def _is_backdrop(
    pixel: tuple[int, int, int], palette: list[tuple[int, int, int]]
) -> bool:
    if any(_distance(pixel, backdrop) <= BACKDROP_TOLERANCE for backdrop in palette):
        return True
    return min(pixel) >= SPARKLE_MINIMUM_CHANNEL


def _flood_backdrop(
    image: Image.Image,
    palette: list[tuple[int, int, int]],
    seeds: list[tuple[int, int]],
) -> bytearray:
    """Mark backdrop pixels reachable from the border or an interior seed.

    Flooding instead of thresholding globally is what protects pale garments: a
    pink skirt matches the backdrop colour, but the character's ink outline means
    the flood never reaches it.
    """
    width, height = image.size
    pixels = image.load()
    is_backdrop = bytearray(width * height)
    queue: deque[int] = deque()

    def visit(x: int, y: int) -> None:
        index = y * width + x
        if is_backdrop[index]:
            return
        if not _is_backdrop(pixels[x, y][:3], palette):
            return
        is_backdrop[index] = 1
        queue.append(index)

    for x in range(width):
        visit(x, 0)
        visit(x, height - 1)
    for y in range(height):
        visit(0, y)
        visit(width - 1, y)
    for x, y in seeds:
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

    return is_backdrop


def _largest_component(mask: bytearray, width: int, height: int) -> bytearray:
    """Keep only the biggest solid shape, dropping frame lines and sparkles."""
    labels = bytearray(width * height)
    best: list[int] = []
    for start in range(width * height):
        if mask[start] == 0 or labels[start]:
            continue
        component: list[int] = []
        queue: deque[int] = deque([start])
        labels[start] = 1
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
                if mask[neighbour] and not labels[neighbour]:
                    labels[neighbour] = 1
                    queue.append(neighbour)
        if len(component) > len(best):
            best = component

    kept = bytearray(width * height)
    for index in best:
        kept[index] = 1
    return kept


def cut_out(source: Path, destination: Path) -> tuple[int, int]:
    image = Image.open(source).convert("RGBA")
    width, height = image.size
    inset = int(min(width, height) * BORDER_INSET)
    palette, seeds = _backdrop_palette(image, inset)

    is_backdrop = _flood_backdrop(image, palette, seeds)
    subject = bytearray(1 if value == 0 else 0 for value in is_backdrop)
    subject = _largest_component(subject, width, height)

    result = image.copy()
    result_pixels = result.load()
    min_x, min_y, max_x, max_y = width, height, -1, -1
    for index, keep in enumerate(subject):
        x = index % width
        y = index // width
        if keep:
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y
        else:
            red, green, blue, _ = result_pixels[x, y]
            result_pixels[x, y] = (red, green, blue, 0)

    if max_x < 0:
        raise SystemExit(f"{source.name}: no subject found")

    box = (
        max(0, min_x - EDGE_PADDING),
        max(0, min_y - EDGE_PADDING),
        min(width, max_x + 1 + EDGE_PADDING),
        min(height, max_y + 1 + EDGE_PADDING),
    )
    cropped = result.crop(box)
    scale = TARGET_HEIGHT / cropped.height
    resized = cropped.resize(
        (max(1, round(cropped.width * scale)), TARGET_HEIGHT),
        Image.LANCZOS,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    resized.save(destination, optimize=True)
    return resized.size


def main() -> int:
    sources = sorted(COMMUNITY_ASSETS.glob("pixel-look-*.png"))
    if not sources:
        print("no source portraits found", file=sys.stderr)
        return 1
    for source in sources:
        destination = OUTPUT_DIR / source.name
        size = cut_out(source, destination)
        kilobytes = destination.stat().st_size / 1024
        print(f"{source.name} -> {destination.relative_to(REPO_ROOT)}  {size[0]}x{size[1]}  {kilobytes:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
