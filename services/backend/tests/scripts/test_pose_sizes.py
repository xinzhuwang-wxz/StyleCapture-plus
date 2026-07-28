"""Every pose of a character must draw the body at one size.

The world scales sprites by frame height, so a character drawn larger in one
pose than another visibly grows and shrinks as it switches between standing,
waving and cheering. That was reported from the demo, and it is invisible to
every other test we have, so it is pinned here against the real assets.
"""

from __future__ import annotations

import pathlib

import pytest
from PIL import Image

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[4]
POSE_ROOT = REPOSITORY_ROOT / "apps/h5/public/assets/community/poses"

ALPHA_FLOOR = 40
HEAD_WIDTH_RATIO = 0.35
MIN_SOLID_RUN = 3
SOLID_RUN_RATIO = 0.05
TOLERANCE = 1.01


def _body_height(path: pathlib.Path) -> int | None:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
        width, height = image.size
        alpha = image.getchannel("A").load()
        runs = [sum(1 for x in range(width) if alpha[x, y] > ALPHA_FLOOR) for y in range(height)]
    widest = max(runs) or 1
    floor = max(MIN_SOLID_RUN, SOLID_RUN_RATIO * widest)
    solid = [y for y, run in enumerate(runs) if run >= floor]
    if not solid:
        return None
    head = next(
        (y for y in range(height) if runs[y] >= HEAD_WIDTH_RATIO * widest),
        solid[0],
    )
    return solid[-1] - head + 1


def _characters() -> list[pathlib.Path]:
    if not POSE_ROOT.is_dir():
        return []
    return sorted(path for path in POSE_ROOT.iterdir() if path.is_dir())


@pytest.mark.parametrize("character", _characters(), ids=lambda path: path.name)
def test_every_pose_matches_the_idle_body_size(character: pathlib.Path) -> None:
    reference = character / "idle.png"
    if not reference.exists():
        pytest.skip(f"{character.name} has no idle frame")
    target = _body_height(reference)
    assert target, f"{character.name}/idle is empty"

    for pose in sorted(character.glob("*.png")):
        measured = _body_height(pose)
        assert measured, f"{character.name}/{pose.stem} is empty"
        drift = max(measured, target) / min(measured, target)
        assert drift <= TOLERANCE, (
            f"{character.name}/{pose.stem} draws the body {measured}px tall but "
            f"idle draws it {target}px. Run "
            f"`uv run python scripts/pixel_pose_normalize.py`."
        )
