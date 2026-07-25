from __future__ import annotations

import shutil
import subprocess
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from stylecapture_backend.features.capture.domain import (
    FeedSelection,
    ImagePayload,
    NormalizedPoint,
)
from stylecapture_backend.features.capture.feed_media import (
    ExtractFrameRequest,
    SegmentationPrompt,
)
from stylecapture_backend.features.capture.infrastructure.feed_media import (
    CoarsePolygonSegmentationProvider,
    FfmpegFrameExtractor,
)
from stylecapture_backend.features.capture.processing import ProviderError


def _make_two_color_video(path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.fail("FFmpeg is required for Feed media extraction tests")
    subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=32x24:d=1:r=5",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=32x24:d=1:r=5",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )


def _selection() -> FeedSelection:
    return FeedSelection(
        selection_key="jacket",
        polygon=(
            NormalizedPoint(0.18, 0.22),
            NormalizedPoint(0.72, 0.20),
            NormalizedPoint(0.68, 0.78),
            NormalizedPoint(0.21, 0.75),
        ),
    )


def test_ffmpeg_extracts_the_requested_frame_and_atomically_publishes_it(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    frame_root = tmp_path / "frames"
    source_root.mkdir()
    source_path = source_root / "feed" / "look.mp4"
    source_path.parent.mkdir()
    _make_two_color_video(source_path)
    extractor = FfmpegFrameExtractor(
        source_root=source_root,
        frame_root=frame_root,
        timeout_seconds=5,
    )

    frame = extractor.extract(
        ExtractFrameRequest(
            source_object_key="feed/look.mp4",
            frame_object_key="feed/look/frame-1200.png",
            timestamp_ms=1_200,
        )
    )

    assert frame.object_key == "feed/look/frame-1200.png"
    assert frame.content_type == "image/png"
    assert frame.sha256 == sha256(frame.body).hexdigest()
    with Image.open(BytesIO(frame.body)) as image:
        assert image.size == (32, 24)
        red, green, blue = image.convert("RGB").getpixel((16, 12))
    assert blue > red
    assert blue > green
    assert (frame_root / frame.object_key).read_bytes() == frame.body
    assert not list(frame_root.rglob("*.extracting-*"))


def test_ffmpeg_rejects_a_source_path_escape_before_starting_a_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extractor = FfmpegFrameExtractor(
        source_root=tmp_path / "source",
        frame_root=tmp_path / "frames",
    )

    def unexpected_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise AssertionError("FFmpeg must not receive an escaped path")

    monkeypatch.setattr(subprocess, "run", unexpected_run)

    with pytest.raises(ProviderError) as error:
        extractor.extract(
            ExtractFrameRequest(
                source_object_key="../private.mp4",
                frame_object_key="feed/frame.png",
                timestamp_ms=0,
            )
        )

    assert error.value.code == "media_source_invalid"
    assert error.value.retryable is False


def test_ffmpeg_timeout_is_retryable_and_leaves_no_partial_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "feed.mp4").write_bytes(b"video-placeholder")
    frame_root = tmp_path / "frames"
    extractor = FfmpegFrameExtractor(
        source_root=source_root,
        frame_root=frame_root,
        timeout_seconds=0.1,
    )

    def timed_out(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=0.1)

    monkeypatch.setattr(subprocess, "run", timed_out)

    with pytest.raises(ProviderError) as error:
        extractor.extract(
            ExtractFrameRequest(
                source_object_key="feed.mp4",
                frame_object_key="feed/frame.png",
                timestamp_ms=300,
            )
        )

    assert error.value.code == "media_extraction_timeout"
    assert error.value.retryable is True
    assert not (frame_root / "feed/frame.png").exists()
    assert not list(frame_root.rglob("*.extracting-*"))


def test_ffmpeg_rejects_an_output_path_escape_before_starting_a_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "feed.mp4").write_bytes(b"video-placeholder")
    extractor = FfmpegFrameExtractor(
        source_root=source_root,
        frame_root=tmp_path / "frames",
    )

    def unexpected_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise AssertionError("FFmpeg must not receive an escaped output path")

    monkeypatch.setattr(subprocess, "run", unexpected_run)

    with pytest.raises(ProviderError) as error:
        extractor.extract(
            ExtractFrameRequest(
                source_object_key="feed.mp4",
                frame_object_key="../frame.png",
                timestamp_ms=0,
            )
        )

    assert error.value.code == "media_frame_key_invalid"
    assert error.value.retryable is False


def test_ffmpeg_failure_uses_an_argument_list_and_removes_partial_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "feed.mp4").write_bytes(b"video-placeholder")
    frame_root = tmp_path / "frames"
    extractor = FfmpegFrameExtractor(
        source_root=source_root,
        frame_root=frame_root,
        ffmpeg_binary="/usr/local/bin/ffmpeg",
    )

    def failed_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        assert isinstance(args, list)
        assert "shell" not in kwargs
        Path(args[-1]).write_bytes(b"partial-frame")
        return subprocess.CompletedProcess(args=args, returncode=1, stdout=b"", stderr=b"failed")

    monkeypatch.setattr(subprocess, "run", failed_run)

    with pytest.raises(ProviderError) as error:
        extractor.extract(
            ExtractFrameRequest(
                source_object_key="feed.mp4",
                frame_object_key="feed/frame.png",
                timestamp_ms=300,
            )
        )

    assert error.value.code == "media_extraction_failed"
    assert error.value.retryable is False
    assert not (frame_root / "feed/frame.png").exists()
    assert not list(frame_root.rglob("*.extracting-*"))


def test_coarse_fallback_preserves_the_user_polygon_without_claiming_a_mask() -> None:
    selection = _selection()
    frame = ImagePayload(
        object_key="feed/look/frame.png",
        content_type="image/png",
        body=b"real-frame",
        sha256=sha256(b"real-frame").hexdigest(),
    )

    result = CoarsePolygonSegmentationProvider().segment(
        SegmentationPrompt(
            frame=frame,
            selection=selection,
            fallback_reason="refinement_provider_unavailable",
        )
    )

    assert result.selection_key == selection.selection_key
    assert result.coarse_polygon == selection.polygon
    assert result.mask is None
    assert result.metadata.refined is False
    assert result.metadata.representation == "coarse_polygon"
    assert result.metadata.provider == "deterministic_lasso_fallback"
    assert result.metadata.fallback_reason == "refinement_provider_unavailable"
