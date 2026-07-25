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
ASSET_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class FeedSourceAsset(BaseModel):
    """A rights-reviewed remote asset before local review transcoding."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_id: str = Field(min_length=1, pattern=ASSET_ID_PATTERN.pattern)
    source_page_url: HttpUrl
    direct_media_url: HttpUrl
    source_platform: Literal["pexels", "pixabay", "mixkit", "wikimedia_commons"]
    creator_name: str = Field(min_length=1)
    license_name: str = Field(min_length=1)
    license_url: HttpUrl
    content_type: Literal["video"]
    category_bucket: Literal[
        "runway",
        "street_style",
        "layering",
        "accessory",
        "shop_negative",
        "low_light_or_historical",
    ]
    orientation: Literal["vertical", "portrait", "square", "horizontal"]
    replacement_note: str = Field(min_length=1)
    fixed_regression: bool
    curated_seed_reason: str = Field(min_length=1)


class FeedAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_id: str = Field(min_length=1, pattern=ASSET_ID_PATTERN.pattern)
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


class FeedCorpusSourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    assets: list[FeedSourceAsset]


def _sha256(path: Path) -> str:
    with path.open("rb") as media:
        return hashlib.file_digest(media, "sha256").hexdigest()


def _probe_video(path: Path, *, asset_id: str) -> None:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise ValueError(f"ffprobe failed for {asset_id}")


def _ingest_source_asset(
    source: FeedSourceAsset,
    *,
    corpus_root: Path,
    clip_duration_seconds: float = 6.0,
) -> FeedAsset:
    """Transcode one remote source through FFmpeg, then atomically publish it."""

    if not 0 < clip_duration_seconds <= 12:
        raise ValueError("clip duration must be between 0 and 12 seconds")

    media_dir = corpus_root / "media"
    staging_dir = corpus_root / ".staging"
    media_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)
    relative_path = Path("media") / f"{source.asset_id}.mp4"
    target_path = corpus_root / relative_path
    staging_path = staging_dir / f"{source.asset_id}.mp4.part"

    if not target_path.exists():
        staging_path.unlink(missing_ok=True)
        command = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-rw_timeout",
            "60000000",
            "-reconnect",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
            "-i",
            str(source.direct_media_url),
            "-t",
            str(clip_duration_seconds),
            "-filter_threads",
            "1",
            "-filter_complex_threads",
            "1",
            "-vf",
            (
                "scale=480:854:force_original_aspect_ratio=decrease,"
                "pad=480:854:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
            ),
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-preset",
            "veryfast",
            "-crf",
            "30",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
            str(staging_path),
        ]
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            staging_path.unlink(missing_ok=True)
            detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown"
            raise ValueError(f"ffmpeg ingest failed for {source.asset_id}: {detail}")
        _probe_video(staging_path, asset_id=source.asset_id)
        staging_path.replace(target_path)

    _probe_video(target_path, asset_id=source.asset_id)
    return FeedAsset(
        asset_id=source.asset_id,
        source_page_url=source.source_page_url,
        source_platform=source.source_platform,
        creator_name=source.creator_name,
        license_name=source.license_name,
        license_url=source.license_url,
        local_path=relative_path.as_posix(),
        content_type=source.content_type,
        category_bucket=source.category_bucket,
        orientation=source.orientation,
        sha256=_sha256(target_path),
        replacement_note=source.replacement_note,
        fixed_regression=source.fixed_regression,
        annotation_provenance="curated_seed",
        curated_seed_reason=source.curated_seed_reason,
    )


def _require_corpus_coverage(
    assets: Sequence[FeedAsset | FeedSourceAsset],
) -> int:
    regression_count = sum(asset.fixed_regression for asset in assets)
    if regression_count < MINIMUM_REGRESSION_COUNT:
        raise ValueError(
            f"manifest must contain at least {MINIMUM_REGRESSION_COUNT} fixed regression assets"
        )
    for category, minimum in CATEGORY_MINIMUMS.items():
        actual = sum(asset.category_bucket == category for asset in assets)
        if actual < minimum:
            raise ValueError(f"category bucket {category} requires at least {minimum} assets")
    return regression_count


def _load_source_manifest(manifest_path: Path) -> FeedCorpusSourceManifest:
    raw_json = manifest_path.read_text(encoding="utf-8")
    raw_payload = json.loads(raw_json)
    raw_assets = raw_payload.get("assets", []) if isinstance(raw_payload, dict) else []
    if len(raw_assets) < MINIMUM_ASSET_COUNT:
        raise ValueError(f"manifest must contain at least {MINIMUM_ASSET_COUNT} assets")
    payload = FeedCorpusSourceManifest.model_validate_json(raw_json)
    for field in ("asset_id", "source_page_url", "direct_media_url"):
        values = [str(getattr(asset, field)) for asset in payload.assets]
        if len(set(values)) != len(values):
            raise ValueError(f"manifest contains duplicate {field}")
    _require_corpus_coverage(payload.assets)
    return payload


def _ingest(
    source_manifest_path: Path,
    output_manifest_path: Path,
    *,
    clip_duration_seconds: float,
) -> tuple[int, int]:
    source_manifest = _load_source_manifest(source_manifest_path)
    output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    assets = [
        _ingest_source_asset(
            source,
            corpus_root=output_manifest_path.parent,
            clip_duration_seconds=clip_duration_seconds,
        )
        for source in source_manifest.assets
    ]
    manifest = FeedCorpusManifest(schema_version=1, assets=assets)
    staging_manifest = output_manifest_path.with_suffix(f"{output_manifest_path.suffix}.part")
    staging_manifest.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    staging_manifest.replace(output_manifest_path)
    return _verify(output_manifest_path, probe_media=True)


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
    regression_count = _require_corpus_coverage(assets)
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
            _probe_video(media_path, asset_id=asset.asset_id)
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
    ingest = subcommands.add_parser(
        "ingest",
        help="sequentially transcode a rights-reviewed source manifest",
    )
    ingest.add_argument("source_manifest", type=Path)
    ingest.add_argument("output_manifest", type=Path)
    ingest.add_argument(
        "--clip-duration",
        type=float,
        default=6.0,
        help="review clip duration in seconds (maximum 12)",
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
        elif arguments.command == "ingest":
            asset_count, regression_count = _ingest(
                arguments.source_manifest,
                arguments.output_manifest,
                clip_duration_seconds=arguments.clip_duration,
            )
            print(f"ingested {asset_count} assets ({regression_count} fixed regression)")
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"feed corpus invalid: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
