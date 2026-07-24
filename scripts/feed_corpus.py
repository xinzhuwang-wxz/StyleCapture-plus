#!/usr/bin/env python3
"""Validate the provenance-recorded StyleCapture review Feed."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

MINIMUM_ASSET_COUNT = 30
MINIMUM_REGRESSION_COUNT = 8
CATEGORY_MINIMUMS = {
    "runway": 8,
    "street_style": 8,
    "layering": 4,
    "accessory": 4,
    "shop_negative": 4,
    "low_light_or_historical": 2,
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class FeedAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_id: str = Field(min_length=1)
    source_page_url: HttpUrl
    source_platform: Literal["pexels", "pixabay", "mixkit", "wikimedia_commons"]
    creator_name: str = Field(min_length=1)
    license_name: str = Field(min_length=1)
    license_url: HttpUrl
    local_path: str = Field(min_length=1)
    content_type: Literal["video", "image"]
    category_bucket: Literal[
        "runway",
        "street_style",
        "layering",
        "accessory",
        "shop_negative",
        "low_light_or_historical",
    ]
    orientation: Literal["vertical", "portrait", "square", "horizontal"]
    sha256: str = Field(pattern=SHA256_PATTERN.pattern)
    replacement_note: str = Field(min_length=1)
    fixed_regression: bool
    annotation_provenance: str
    curated_seed_reason: str = Field(min_length=1)

    @field_validator("annotation_provenance")
    @classmethod
    def require_curated_seed(cls, value: str) -> str:
        if value != "curated_seed":
            raise ValueError("annotation_provenance must be curated_seed")
        return value


class FeedCorpusManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    assets: list[FeedAsset]


def _verify(manifest_path: Path, *, probe_media: bool) -> tuple[int, int]:
    raw_json = manifest_path.read_text(encoding="utf-8")
    raw_payload = json.loads(raw_json)
    raw_assets = raw_payload.get("assets", []) if isinstance(raw_payload, dict) else []
    if len(raw_assets) < MINIMUM_ASSET_COUNT:
        raise ValueError(f"manifest must contain at least {MINIMUM_ASSET_COUNT} assets")
    payload = FeedCorpusManifest.model_validate_json(raw_json)
    assets = payload.assets
    for field in ("asset_id", "source_page_url", "sha256"):
        values = [getattr(asset, field) for asset in assets]
        if len(set(values)) != len(values):
            raise ValueError(f"manifest contains duplicate {field}")
    regression_count = sum(asset.fixed_regression for asset in assets)
    if regression_count < MINIMUM_REGRESSION_COUNT:
        raise ValueError(
            f"manifest must contain at least {MINIMUM_REGRESSION_COUNT} fixed regression assets"
        )
    for category, minimum in CATEGORY_MINIMUMS.items():
        actual = sum(asset.category_bucket == category for asset in assets)
        if actual < minimum:
            raise ValueError(f"category bucket {category} requires at least {minimum} assets")
    corpus_root = manifest_path.resolve().parent
    for asset in assets:
        expected_sha256 = asset.sha256.lower()
        media_path = (corpus_root / asset.local_path).resolve()
        if not media_path.is_relative_to(corpus_root):
            raise ValueError(f"local_path escapes corpus root for {asset.asset_id}")
        try:
            with media_path.open("rb") as media:
                digest = hashlib.file_digest(media, "sha256").hexdigest()
        except FileNotFoundError as error:
            raise ValueError(f"media file missing for {asset.asset_id}") from error
        if digest != expected_sha256:
            raise ValueError(f"sha256 mismatch for {asset.asset_id}")
        if probe_media:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "stream=codec_type,width,height:format=duration",
                    "-of",
                    "json",
                    str(media_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise ValueError(f"ffprobe failed for {asset.asset_id}")
    return len(assets), regression_count


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    verify = subcommands.add_parser("verify", help="validate a Feed corpus manifest")
    verify.add_argument("manifest", type=Path)
    verify.add_argument(
        "--skip-media-probe",
        action="store_true",
        help="validate metadata only; intended for unit tests and manifest drafting",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "verify":
            asset_count, regression_count = _verify(
                arguments.manifest,
                probe_media=not arguments.skip_media_probe,
            )
            print(f"verified {asset_count} assets ({regression_count} fixed regression)")
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"feed corpus invalid: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
