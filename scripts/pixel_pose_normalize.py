"""Make every pose of a character the same body size.

`pixel_sprite.py` normalises each source portrait on its own. That is not enough:
a character can be drawn larger in one pose than another in the source art, and
the world scales sprites by frame height, so the figure visibly grows and shrinks
as it switches between standing, waving and cheering.

This pass takes each character's `idle` frame as the reference and rescales the
other poses about the feet line until head-to-feet matches. Canvas size and the
feet row are preserved, so the contact shadow and the ground line do not move.

Run:  uv run python scripts/pixel_pose_normalize.py [--check]
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Any, cast

from PIL import Image

POSE_ROOT = pathlib.Path("apps/h5/public/assets/community/poses")
REFERENCE_POSE = "idle"

# Matched to pixel_sprite.py so both passes agree on what "the body" is.
ALPHA_FLOOR = 40
HEAD_WIDTH_RATIO = 0.35
MIN_SOLID_RUN = 3
SOLID_RUN_RATIO = 0.05

# Below this the difference is invisible at world scale (sprites draw ~40px tall)
# and rescaling would cost more resampling blur than it buys.
TOLERANCE = 1.01


def measure(image: Image.Image) -> tuple[int, int] | None:
    """Return (head_top_row, feet_row) for the drawn body."""
    width, height = image.size
    alpha = cast(Any, image.getchannel("A").load())
    runs = [sum(1 for x in range(width) if alpha[x, y] > ALPHA_FLOOR) for y in range(height)]
    widest = max(runs) or 1
    floor = max(MIN_SOLID_RUN, SOLID_RUN_RATIO * widest)
    solid = [y for y, run in enumerate(runs) if run >= floor]
    if not solid:
        return None
    feet = solid[-1]
    head = next(
        (y for y in range(height) if runs[y] >= HEAD_WIDTH_RATIO * widest),
        solid[0],
    )
    return head, feet


def body_height(image: Image.Image) -> int | None:
    measured = measure(image)
    return None if measured is None else measured[1] - measured[0] + 1


def rescale_to(image: Image.Image, ratio: float) -> Image.Image:
    """Scale the drawing by `ratio` while keeping the canvas and the feet row."""
    width, height = image.size
    measured = measure(image)
    assert measured is not None
    _, feet = measured

    scaled = image.resize(
        (max(1, round(width * ratio)), max(1, round(height * ratio))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    # Keep the feet where they were so the shadow and ground contact do not move.
    left = round((width - scaled.width) / 2)
    top = round(feet - (feet * ratio))
    canvas.paste(scaled, (left, top))
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift without writing; exit 1 if any character is uneven",
    )
    args = parser.parse_args()

    if not POSE_ROOT.is_dir():
        print(f"pose directory not found: {POSE_ROOT}", file=sys.stderr)
        return 2

    uneven = 0
    for character in sorted(p for p in POSE_ROOT.iterdir() if p.is_dir()):
        reference_path = character / f"{REFERENCE_POSE}.png"
        if not reference_path.exists():
            print(f"{character.name}: no {REFERENCE_POSE} frame, skipped")
            continue
        with Image.open(reference_path) as image:
            target = body_height(image.convert("RGBA"))
        if not target:
            print(f"{character.name}: {REFERENCE_POSE} frame is empty, skipped")
            continue

        for pose_path in sorted(character.glob("*.png")):
            if pose_path.stem == REFERENCE_POSE:
                continue
            with Image.open(pose_path) as opened:
                frame = opened.convert("RGBA")
                current = body_height(frame)
                if not current:
                    continue
                drift = max(current, target) / min(current, target)
                if drift <= TOLERANCE:
                    continue
                uneven += 1
                label = f"{character.name}/{pose_path.stem}"
                if args.check:
                    print(f"{label}: {current}px vs {REFERENCE_POSE} {target}px")
                    continue
                fixed = rescale_to(frame, target / current)
                fixed.save(pose_path)
                print(f"{label}: {current}px -> {body_height(fixed)}px")

    if args.check and uneven:
        print(f"\n{uneven} pose(s) differ from their idle frame", file=sys.stderr)
        return 1
    if not uneven:
        print("every pose already matches its idle frame")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
