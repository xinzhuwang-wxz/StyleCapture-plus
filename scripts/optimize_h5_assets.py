"""Downscale and quantize the StyleCapture design assets for the H5 bundle.

The handoff bundle ships 1254px pixel-art PNGs (~1.3MB each). The H5 app never
renders them wider than ~340 CSS px at 2x, so they are resized to the largest
size the UI actually uses and quantized to a palette. Run from the repo root:

    python3 scripts/optimize_h5_assets.py <source-dir> <target-dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

# name prefix -> longest edge kept after resize
BUDGETS = {
    "item-": 512,
    "pixel-": 640,
    "collage-": 768,
    "real-": 900,
}


def budget_for(name: str) -> int:
    for prefix, size in BUDGETS.items():
        if name.startswith(prefix):
            return size
    return 640


def optimize(source: Path, target: Path) -> tuple[int, int]:
    image = Image.open(source)
    longest = budget_for(source.stem)
    scale = min(1.0, longest / max(image.size))
    if scale < 1.0:
        size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(size, Image.LANCZOS)

    if source.suffix.lower() in {".jpg", ".jpeg"}:
        image.convert("RGB").save(target, "JPEG", quality=82, optimize=True, progressive=True)
    else:
        # Pixel art survives a 128-colour palette without visible banding and
        # drops the payload by roughly an order of magnitude. FASTOCTREE is the
        # only Pillow method that quantizes RGBA without dropping the alpha.
        image.convert("RGBA").quantize(colors=128, method=Image.FASTOCTREE).save(
            target, "PNG", optimize=True
        )
    return source.stat().st_size, target.stat().st_size


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    source_dir = Path(sys.argv[1])
    target_dir = Path(sys.argv[2])
    target_dir.mkdir(parents=True, exist_ok=True)

    before = after = 0
    for source in sorted(source_dir.iterdir()):
        if source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        target = target_dir / source.name
        was, now = optimize(source, target)
        before += was
        after += now
        print(f"{source.name:<20} {was // 1024:>6} KB -> {now // 1024:>5} KB")

    print(f"\ntotal {before // 1024} KB -> {after // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
