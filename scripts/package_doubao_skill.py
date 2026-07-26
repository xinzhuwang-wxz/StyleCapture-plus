#!/usr/bin/env python3
"""Validate and build a deterministic, shareable Doubao try-on skill archive."""

from __future__ import annotations

import argparse
import re
import stat
import sys
import zipfile
from pathlib import Path

VERSION = "1.2.0"
REQUIRED_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "references/api-contract.md",
    "scripts/virtual_try_on.py",
    "scripts/batch_virtual_try_on.py",
)
EXCLUDED_PARTS = {"__pycache__", ".DS_Store"}


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Validate and package the Doubao virtual try-on Codex skill."
    )
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=repo_root / "skills" / "doubao-virtual-try-on",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(repo_root / "dist" / "skills" / f"doubao-virtual-try-on-v{VERSION}.zip"),
    )
    return parser.parse_args()


def validate(skill_dir: Path) -> list[Path]:
    skill_dir = skill_dir.expanduser().resolve()
    if not skill_dir.is_dir():
        raise ValueError(f"Skill directory not found: {skill_dir}")

    for relative in REQUIRED_FILES:
        path = skill_dir / relative
        if not path.is_file():
            raise ValueError(f"Required skill file missing: {relative}")

    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    if not skill_text.startswith("---\n") or "name: doubao-virtual-try-on" not in skill_text:
        raise ValueError("SKILL.md frontmatter is missing the expected skill name")

    files: list[Path] = []
    credential_pattern = re.compile(r"\bark-[A-Za-z0-9_-]{20,}\b")
    for path in sorted(skill_dir.rglob("*")):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Symlinks are not allowed in the archive: {path}")
        if not path.is_file() or path.suffix == ".pyc":
            continue
        if credential_pattern.search(path.read_text(encoding="utf-8")):
            raise ValueError(f"Possible embedded Ark credential found in: {path}")
        files.append(path)
    return files


def build_archive(skill_dir: Path, output: Path, files: list[Path]) -> None:
    skill_dir = skill_dir.expanduser().resolve()
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = Path(skill_dir.name) / path.relative_to(skill_dir)
            info = zipfile.ZipInfo(str(relative), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = path.stat().st_mode
            permissions = 0o755 if mode & stat.S_IXUSR else 0o644
            info.external_attr = (stat.S_IFREG | permissions) << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    args = parse_args()
    skill_dir = args.skill_dir.expanduser().resolve()
    files = validate(skill_dir)
    build_archive(skill_dir, args.output, files)
    print(f"Validated {len(files)} files")
    print(f"ARCHIVE={args.output.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
