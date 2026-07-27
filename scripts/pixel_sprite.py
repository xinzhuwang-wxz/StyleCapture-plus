"""Normalise character artwork so every sprite draws at the same body size.

Trimming a character to its bounding box and scaling that to a fixed height
looks correct until you compare poses: a cheering figure's box includes the
raised arms, so the *person* inside it comes out smaller than the same person
standing still. Hand-cropped source files make it worse — some arrived with the
character drawn at two thirds the scale of the rest of their own pose set.

The fix is to measure the character rather than the picture. Standing height is
the distance from the top of the head to the feet, and the head is found by
ignoring rows that are too narrow to be anything but a raised arm. Every sprite
is then scaled so that distance is the same fraction of the output, and placed
so the feet sit on the canvas floor and the feet's centre is the canvas centre.

The renderer can then draw any sprite at one height, anchored at the feet, and
characters keep their size through every pose and every interaction.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

#: Output canvas height for every sprite.
TARGET_HEIGHT = 360
#: Share of the canvas taken by the standing body, leaving room for raised arms.
BODY_FRACTION = 0.78
#: Rows narrower than this share of the widest row are limbs, not the head.
HEAD_WIDTH_RATIO = 0.35
#: Opaque cutoff; anti-aliased edges should not count as body.
ALPHA_FLOOR = 40
#: A row must contain a run at least this wide to count as part of the body.
#: Hand-cropped sources carry faint one-pixel edge artefacts running the full
#: height of the frame; read as feet, they put the character in mid-air.
SOLID_RUN_RATIO = 0.05
MIN_SOLID_RUN = 3


@dataclass(frozen=True)
class Anatomy:
    """Where the character is inside its picture."""

    head_top: int
    feet: int
    feet_center: float
    left: int
    right: int

    @property
    def standing_height(self) -> int:
        return self.feet - self.head_top


def _widest_run(row: list[int]) -> int:
    best = current = 0
    for value in row:
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def measure(image: Image.Image) -> Anatomy | None:
    """Locates the head, the feet, and the point the character stands on.

    Extents come from a thresholded mask rather than `getbbox`, which counts
    alpha-1 pixels. Several sources carry an almost invisible drop shadow below
    the feet; trusting it put the feet a hundred rows too low, and the shadow
    then vanished on downscale, leaving the character hovering.
    """
    alpha = image.split()[3].load()
    width, height = image.size
    mask = [
        [1 if alpha[x, y] > ALPHA_FLOOR else 0 for x in range(width)]
        for y in range(height)
    ]
    runs = [_widest_run(row) for row in mask]
    widest = max(runs)
    if widest == 0:
        return None

    floor = max(MIN_SOLID_RUN, SOLID_RUN_RATIO * widest)
    solid_rows = [y for y in range(height) if runs[y] >= floor]
    if not solid_rows:
        return None
    top, feet = solid_rows[0], solid_rows[-1] + 1
    column_counts = [
        sum(mask[y][x] for y in solid_rows) for x in range(width)
    ]
    solid_columns = [x for x in range(width) if column_counts[x] >= MIN_SOLID_RUN]
    if not solid_columns:
        return None
    left, right = solid_columns[0], solid_columns[-1] + 1

    head_top = next(
        (y for y in range(height) if runs[y] >= HEAD_WIDTH_RATIO * widest),
        top,
    )

    # Centre on the feet rather than the bounding box: an outstretched arm must
    # not shift where the character appears to be standing.
    sole_band = max(1, round((feet - head_top) * 0.06))
    columns: list[int] = []
    for y in range(max(top, feet - sole_band), feet):
        columns.extend(x for x in range(width) if mask[y][x])
    feet_center = sum(columns) / len(columns) if columns else (left + right) / 2

    return Anatomy(head_top, feet, feet_center, left, right)


def normalise(image: Image.Image) -> Image.Image:
    """Returns the character on a canvas where body size is always the same."""
    anatomy = measure(image)
    if anatomy is None or anatomy.standing_height <= 0:
        raise ValueError("no character found in image")

    scale = (TARGET_HEIGHT * BODY_FRACTION) / anatomy.standing_height
    scaled = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.LANCZOS,
    )

    feet_y = anatomy.feet * scale
    feet_x = anatomy.feet_center * scale
    # Symmetric around the feet so the character never drifts off its own mark.
    reach = max(feet_x - anatomy.left * scale, anatomy.right * scale - feet_x)
    canvas_width = max(2, round(reach * 2) + 2)

    canvas = Image.new("RGBA", (canvas_width, TARGET_HEIGHT), (0, 0, 0, 0))
    canvas.alpha_composite(
        scaled,
        (round(canvas_width / 2 - feet_x), round(TARGET_HEIGHT - feet_y)),
    )
    return canvas
