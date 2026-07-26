"""Turn the supplied pose pack into named character sprites.

The pack in `像素小人动作包/` is four characters photographed in four poses each,
delivered as 1024x1536 transparent PNGs with opaque-UUID filenames. This script
trims each one to its subject, scales it to a common height, and writes it under
a readable `poses/<character>/<pose>.png` path so the runtime can swap poses by
name.

Run offline whenever the pack changes:

    uv run python scripts/pixel_pose_cutout.py

Poses are authored art, so no background removal is needed — only trimming and
resizing. The mapping below is the one piece of human knowledge in the pipeline
and is recorded explicitly rather than guessed at runtime.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "像素小人动作包"
OUTPUT_DIR = REPO_ROOT / "apps/h5/public/assets/community/poses"

TARGET_HEIGHT = 360

# character -> pose -> source stem
POSE_PACK: dict[str, dict[str, str]] = {
    "ash": {
        "idle": "a0aed68a-4242-4b57-bad8-003c0bc21530",
        "wave": "b10a7daf-32f1-4c5c-8b2f-e6538e93c1af",
        "cheer": "9312aa09-e19c-48ab-870f-142f0c05074a",
        "walk": "1006868d-0494-47b6-9b1f-26a9cc50484d",
    },
    "cargo": {
        "idle": "f8ba107d-26a4-429a-ad43-9f962035593c",
        "wave": "1ab196cf-e791-4a38-89b8-bd5e144eb0a8",
        "cheer": "434bed2d-172d-46d1-a587-03e50eaef99e",
        "walk": "462c384d-9e99-417e-b56b-031c8226b4e8",
    },
    "linen": {
        "idle": "f4c7ffba-b631-4024-948a-44c470450c8f",
        "wave": "212afffa-5fe3-4921-8401-14e52e8479d1",
        "cheer": "a04d3745-a9dd-4684-ae37-b415edbc06de",
        "walk": "91391638-f023-48bf-9a9c-02a3100869b6",
    },
    "jersey": {
        "idle": "79442189-e9ca-46c4-8d65-12944b75a62b",
        "wave": "f720e68c-0cf1-49d1-a77e-8cc5ff94107d",
        "cheer": "3735c1e1-4d82-4ae6-bdfe-ca4581781ae9",
        "walk": "d89a5a6b-55bc-452c-b145-366b26debc60",
    },
}


def trim_to_subject(image: Image.Image) -> Image.Image:
    box = image.getbbox()
    if box is None:
        raise SystemExit("empty image")
    return image.crop(box)


def build(character: str, pose: str, stem: str) -> tuple[int, int, float]:
    source = SOURCE_DIR / f"{stem}.png"
    if not source.exists():
        raise SystemExit(f"missing source for {character}/{pose}: {source.name}")

    image = Image.open(source).convert("RGBA")
    cropped = trim_to_subject(image)
    scale = TARGET_HEIGHT / cropped.height
    resized = cropped.resize(
        (max(1, round(cropped.width * scale)), TARGET_HEIGHT), Image.LANCZOS
    )

    destination = OUTPUT_DIR / character / f"{pose}.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    resized.save(destination, optimize=True)
    return resized.width, resized.height, destination.stat().st_size / 1024


def main() -> int:
    if not SOURCE_DIR.exists():
        print(f"pose pack not found at {SOURCE_DIR}", file=sys.stderr)
        return 1

    stems = {path.stem for path in SOURCE_DIR.glob("*.png")}
    mapped = {stem for poses in POSE_PACK.values() for stem in poses.values()}
    unmapped = stems - mapped
    if unmapped:
        print(f"warning: {len(unmapped)} unmapped source files", file=sys.stderr)

    for character, poses in POSE_PACK.items():
        for pose, stem in poses.items():
            width, height, kilobytes = build(character, pose, stem)
            print(f"{character}/{pose}  {width}x{height}  {kilobytes:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
