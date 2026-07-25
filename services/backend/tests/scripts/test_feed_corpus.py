from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pydantic import HttpUrl

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.feed_corpus import FeedSourceAsset, _ingest_source_asset  # noqa: E402

SCRIPT = REPOSITORY_ROOT / "scripts" / "feed_corpus.py"


def _asset(index: int, *, regression: bool = False) -> dict[str, object]:
    return {
        "asset_id": f"asset-{index:02d}",
        "source_page_url": f"https://example.test/assets/{index}",
        "source_platform": "pexels",
        "creator_name": f"Creator {index}",
        "license_name": "Pexels License",
        "license_url": "https://www.pexels.com/license/",
        "local_path": f"media/asset-{index:02d}.mp4",
        "content_type": "video",
        "category_bucket": "street_style",
        "orientation": "vertical",
        "sha256": f"{index:064x}",
        "replacement_note": "Replace with the same bucket and orientation.",
        "fixed_regression": regression,
        "annotation_provenance": "curated_seed",
        "curated_seed_reason": "Prepared manually for the non-commercial review corpus.",
    }


def _covered_assets(tmp_path: Path) -> list[dict[str, object]]:
    categories = (
        ["runway"] * 8
        + ["street_style"] * 8
        + ["layering"] * 4
        + ["accessory"] * 4
        + ["shop_negative"] * 4
        + ["low_light_or_historical"] * 2
    )
    media = tmp_path / "media"
    media.mkdir()
    assets: list[dict[str, object]] = []
    for index, category in enumerate(categories):
        content = f"asset-content-{index}".encode()
        (media / f"asset-{index:02d}.mp4").write_bytes(content)
        asset = _asset(index, regression=index < 8)
        asset["category_bucket"] = category
        asset["sha256"] = hashlib.sha256(content).hexdigest()
        assets.append(asset)
    return assets


def test_verify_rejects_a_corpus_smaller_than_the_review_minimum(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [{"asset_id": f"asset-{index:02d}"} for index in range(29)],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", str(manifest), "--skip-media-probe"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "at least 30 assets" in result.stderr


def test_verify_rejects_assets_without_item_level_rights_evidence(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [{"asset_id": f"asset-{index:02d}"} for index in range(30)],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", str(manifest), "--skip-media-probe"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "source_page_url" in result.stderr


def test_verify_requires_eight_fixed_regression_assets(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [_asset(index, regression=index < 7) for index in range(30)],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", str(manifest), "--skip-media-probe"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "at least 8 fixed regression assets" in result.stderr


def test_verify_rejects_duplicate_asset_identity(tmp_path: Path) -> None:
    assets = [_asset(index, regression=index < 8) for index in range(30)]
    assets[-1]["asset_id"] = assets[0]["asset_id"]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": 1, "assets": assets}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", str(manifest), "--skip-media-probe"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "duplicate asset_id" in result.stderr


def test_verify_enforces_the_agreed_difficult_case_coverage(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [_asset(index, regression=index < 8) for index in range(30)],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", str(manifest), "--skip-media-probe"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "category bucket runway requires at least 8 assets" in result.stderr


def test_verify_rejects_content_that_does_not_match_the_recorded_hash(tmp_path: Path) -> None:
    assets = _covered_assets(tmp_path)
    assets[-1]["sha256"] = "f" * 64
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": 1, "assets": assets}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", str(manifest), "--skip-media-probe"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "sha256 mismatch for asset-29" in result.stderr


def test_verify_probes_video_playability_unless_explicitly_skipped(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": _covered_assets(tmp_path),
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", str(manifest)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "ffprobe failed for asset-00" in result.stderr


def test_verify_forbids_manual_feed_labels_from_claiming_model_provenance(
    tmp_path: Path,
) -> None:
    assets = _covered_assets(tmp_path)
    assets[0]["annotation_provenance"] = "model"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": 1, "assets": assets}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", str(manifest), "--skip-media-probe"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "annotation_provenance must be curated_seed" in result.stderr


def test_verify_reports_the_accepted_corpus_summary(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": _covered_assets(tmp_path),
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", str(manifest), "--skip-media-probe"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "verified 30 assets (8 fixed regression)"


def test_ingest_source_asset_transcodes_real_video_atomically(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_video = source_root / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=purple:s=720x1280:d=1",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source_video),
        ],
        check=True,
        timeout=20,
    )

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: QuietHandler(*args, directory=source_root, **kwargs),
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        source = FeedSourceAsset(
            asset_id="asset-ingest",
            source_page_url=HttpUrl("https://www.pexels.com/video/example-1/"),
            direct_media_url=HttpUrl(f"http://127.0.0.1:{server.server_port}/{source_video.name}"),
            source_platform="pexels",
            creator_name="Example Creator",
            license_name="Pexels License",
            license_url=HttpUrl("https://www.pexels.com/license/"),
            content_type="video",
            category_bucket="street_style",
            orientation="vertical",
            replacement_note="Replace with the same bucket and orientation.",
            fixed_regression=True,
            curated_seed_reason="Prepared manually for the non-commercial review corpus.",
        )

        asset = _ingest_source_asset(
            source,
            corpus_root=tmp_path / "corpus",
            clip_duration_seconds=0.5,
        )
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)

    media_path = tmp_path / "corpus" / asset.local_path
    assert media_path.exists()
    assert asset.sha256 == hashlib.sha256(media_path.read_bytes()).hexdigest()
    assert asset.annotation_provenance == "curated_seed"
    assert not list((tmp_path / "corpus").rglob("*.part"))

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            str(media_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    dimensions = json.loads(probe.stdout)["streams"][0]
    assert dimensions == {"width": 480, "height": 854}


def test_ingest_rejects_an_incomplete_source_manifest_before_download(
    tmp_path: Path,
) -> None:
    source_manifest = tmp_path / "sources.json"
    source_manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [
                    {
                        "asset_id": f"source-{index:02d}",
                        "source_page_url": f"https://www.pexels.com/video/example-{index}/",
                        "direct_media_url": f"https://videos.pexels.com/example-{index}.mp4",
                        "source_platform": "pexels",
                        "creator_name": f"Creator {index}",
                        "license_name": "Pexels License",
                        "license_url": "https://www.pexels.com/license/",
                        "content_type": "video",
                        "category_bucket": "street_style",
                        "orientation": "vertical",
                        "replacement_note": "Replace with the same bucket and orientation.",
                        "fixed_regression": index < 8,
                        "curated_seed_reason": (
                            "Prepared manually for the non-commercial review corpus."
                        ),
                    }
                    for index in range(29)
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "ingest",
            str(source_manifest),
            str(tmp_path / "corpus" / "manifest.json"),
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "at least 30 assets" in result.stderr
    assert not (tmp_path / "corpus").exists()
