from __future__ import annotations

import shutil
import subprocess
import sys
import types
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
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
    SAM2_TINY_MODEL_ID,
    SAM2_TINY_REVISION,
    CoarsePolygonSegmentationProvider,
    FfmpegFrameExtractor,
    PillowSelectionImageRenderer,
    Sam2MaskCandidate,
    Sam2PromptableSegmentationProvider,
    TransformersSam2Backend,
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


def _png_payload(*, size: tuple[int, int] = (10, 8)) -> ImagePayload:
    output = BytesIO()
    Image.new("RGB", size, color=(120, 80, 200)).save(output, format="PNG")
    body = output.getvalue()
    return ImagePayload(
        object_key="feed/look/frame.png",
        content_type="image/png",
        body=body,
        sha256=sha256(body).hexdigest(),
    )


class RecordingSam2Backend:
    def __init__(self, candidates: tuple[Sam2MaskCandidate, ...]) -> None:
        self.candidates = candidates
        self.calls: list[tuple[tuple[int, int], tuple[int, int, int, int]]] = []

    def segment_box(
        self,
        image: Image.Image,
        box: tuple[int, int, int, int],
    ) -> tuple[Sam2MaskCandidate, ...]:
        self.calls.append((image.size, box))
        return self.candidates


def test_pillow_renderer_isolates_the_coarse_selection_as_a_real_png() -> None:
    source = BytesIO()
    Image.new("RGB", (100, 80), color=(120, 80, 200)).save(source, format="PNG")
    frame_body = source.getvalue()
    frame = ImagePayload(
        object_key="originals/feed/frame.png",
        content_type="image/png",
        body=frame_body,
        sha256=sha256(frame_body).hexdigest(),
    )
    selection = _selection()
    segmentation = CoarsePolygonSegmentationProvider().segment(
        SegmentationPrompt(
            frame=frame,
            selection=selection,
            fallback_reason="refinement_unavailable",
        )
    )

    selected = PillowSelectionImageRenderer().render(frame, segmentation)

    assert selected.object_key.endswith("#selection=jacket")
    assert selected.content_type == "image/png"
    assert selected.sha256 == sha256(selected.body).hexdigest()
    with Image.open(BytesIO(selected.body)) as rendered:
        assert rendered.mode == "RGBA"
        assert 0 < rendered.width < 100
        assert 0 < rendered.height < 80
        assert rendered.getchannel("A").getextrema() == (0, 255)


def test_sam2_provider_converts_prompt_polygon_to_pixel_box_and_full_frame_mask() -> None:
    # Catches: using normalized box values or returning a cropped mask instead of a full-frame PNG.
    mask = Image.new("L", (10, 8), 0)
    ImageDraw.Draw(mask).rectangle((2, 2, 7, 6), fill=255)
    backend = RecordingSam2Backend((Sam2MaskCandidate(mask=mask, score=0.93),))
    provider = Sam2PromptableSegmentationProvider(
        backend_factory=lambda: backend,
        score_threshold=0.5,
    )
    selection = FeedSelection(
        selection_key="coat",
        polygon=(
            NormalizedPoint(0.20, 0.25),
            NormalizedPoint(0.80, 0.25),
            NormalizedPoint(0.80, 0.75),
            NormalizedPoint(0.20, 0.75),
        ),
    )

    result = provider.segment(
        SegmentationPrompt(
            frame=_png_payload(size=(10, 8)),
            selection=selection,
            fallback_reason="refinement_unavailable",
        )
    )

    assert backend.calls == [((10, 8), (2, 2, 7, 5))]
    assert result.selection_key == "coat"
    assert result.coarse_polygon == selection.polygon
    assert result.mask is not None
    assert result.mask.object_key == "feed/look/frame.png#mask=coat"
    assert result.mask.content_type == "image/png"
    assert result.mask.sha256 == sha256(result.mask.body).hexdigest()
    with Image.open(BytesIO(result.mask.body)) as refined:
        assert refined.mode == "L"
        assert refined.size == (10, 8)
        assert refined.getbbox() == (2, 2, 8, 7)


def test_sam2_provider_selects_highest_quality_non_empty_mask_and_metadata() -> None:
    # Catches: accepting the first mask, accepting empty masks, or omitting refined metadata.
    empty = Image.new("L", (10, 8), 0)
    weaker = Image.new("L", (10, 8), 0)
    ImageDraw.Draw(weaker).rectangle((1, 1, 2, 2), fill=255)
    best = Image.new("L", (10, 8), 0)
    ImageDraw.Draw(best).rectangle((4, 3, 8, 6), fill=255)
    provider = Sam2PromptableSegmentationProvider(
        backend_factory=lambda: RecordingSam2Backend(
            (
                Sam2MaskCandidate(mask=empty, score=0.99),
                Sam2MaskCandidate(mask=weaker, score=0.71),
                Sam2MaskCandidate(mask=best, score=0.94),
            )
        ),
        score_threshold=0.7,
    )

    result = provider.segment(
        SegmentationPrompt(
            frame=_png_payload(size=(10, 8)),
            selection=_selection(),
            fallback_reason="refinement_unavailable",
        )
    )

    assert result.metadata.refined is True
    assert result.metadata.representation == "refined_mask"
    assert result.metadata.capability_alias == "local_promptable_segmentation"
    assert result.metadata.model_alias == "segmentation_refinement"
    assert result.metadata.score == pytest.approx(0.94)
    assert result.metadata.fallback_reason is None
    assert result.metadata.latency_ms >= 0
    assert result.mask is not None
    with Image.open(BytesIO(result.mask.body)) as refined:
        assert refined.getbbox() == (4, 3, 9, 7)


def test_sam2_provider_loads_runtime_once_per_process() -> None:
    # Catches: constructing the heavy Transformers runtime for every segmentation.
    loads = 0
    mask = Image.new("L", (10, 8), 0)
    ImageDraw.Draw(mask).rectangle((2, 2, 7, 6), fill=255)

    def load_backend() -> RecordingSam2Backend:
        nonlocal loads
        loads += 1
        return RecordingSam2Backend((Sam2MaskCandidate(mask=mask, score=0.91),))

    provider = Sam2PromptableSegmentationProvider(
        backend_factory=load_backend,
        score_threshold=0.5,
    )
    prompt = SegmentationPrompt(
        frame=_png_payload(size=(10, 8)),
        selection=_selection(),
        fallback_reason="refinement_unavailable",
    )

    provider.segment(prompt)
    provider.segment(prompt)

    assert loads == 1


def test_transformers_sam2_backend_pins_revision_and_disables_remote_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeProcessor:
        @classmethod
        def from_pretrained(cls, model: str, **kwargs: object) -> FakeProcessor:
            calls.append((f"processor:{model}", kwargs))
            return cls()

    class FakeModel:
        @classmethod
        def from_pretrained(cls, model: str, **kwargs: object) -> FakeModel:
            calls.append((f"model:{model}", kwargs))
            return cls()

        def to(self, device: str) -> FakeModel:
            calls.append((f"device:{device}", {}))
            return self

        def eval(self) -> None:
            calls.append(("eval", {}))

    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        types.SimpleNamespace(Sam2Model=FakeModel, Sam2Processor=FakeProcessor),
    )

    TransformersSam2Backend(device="cpu")

    assert calls[0] == (
        f"processor:{SAM2_TINY_MODEL_ID}",
        {"revision": SAM2_TINY_REVISION, "trust_remote_code": False},
    )
    assert calls[1] == (
        f"model:{SAM2_TINY_MODEL_ID}",
        {
            "revision": SAM2_TINY_REVISION,
            "trust_remote_code": False,
            "use_safetensors": True,
        },
    )


@pytest.mark.parametrize(
    ("candidates", "reason"),
    [
        ((), "refinement_model_unavailable"),
        (
            (Sam2MaskCandidate(mask=Image.new("L", (10, 8), 0), score=0.99),),
            "refinement_empty_mask",
        ),
        (
            (
                Sam2MaskCandidate(
                    mask=Image.new("L", (10, 8), 255),
                    score=0.42,
                ),
            ),
            "refinement_low_score",
        ),
    ],
)
def test_sam2_provider_falls_back_truthfully_without_changing_selection_identity(
    candidates: tuple[Sam2MaskCandidate, ...],
    reason: str,
) -> None:
    # Catches: presenting fallback results as refined or losing the user's selected identity.
    selection = _selection()
    provider = Sam2PromptableSegmentationProvider(
        backend_factory=lambda: RecordingSam2Backend(candidates),
        score_threshold=0.8,
    )

    result = provider.segment(
        SegmentationPrompt(
            frame=_png_payload(size=(10, 8)),
            selection=selection,
            fallback_reason="refinement_unavailable",
        )
    )

    assert result.selection_key == selection.selection_key
    assert result.coarse_polygon == selection.polygon
    assert result.mask is None
    assert result.metadata.refined is False
    assert result.metadata.representation == "coarse_polygon"
    assert result.metadata.capability_alias == "deterministic_lasso_fallback"
    assert result.metadata.fallback_reason == reason


def test_sam2_provider_falls_back_when_runtime_load_or_inference_fails() -> None:
    # Catches: surfacing optional local-model failures as hard product failures.
    selection = _selection()

    def unavailable_backend() -> RecordingSam2Backend:
        raise RuntimeError("transformers unavailable")

    result = Sam2PromptableSegmentationProvider(
        backend_factory=unavailable_backend,
        score_threshold=0.8,
    ).segment(
        SegmentationPrompt(
            frame=_png_payload(size=(10, 8)),
            selection=selection,
            fallback_reason="refinement_unavailable",
        )
    )

    assert result.selection_key == selection.selection_key
    assert result.mask is None
    assert result.metadata.refined is False
    assert result.metadata.fallback_reason == "refinement_model_unavailable"

    class FailingBackend(RecordingSam2Backend):
        def segment_box(
            self,
            image: Image.Image,
            box: tuple[int, int, int, int],
        ) -> tuple[Sam2MaskCandidate, ...]:
            raise RuntimeError("inference timeout")

    result = Sam2PromptableSegmentationProvider(
        backend_factory=lambda: FailingBackend(()),
        score_threshold=0.8,
    ).segment(
        SegmentationPrompt(
            frame=_png_payload(size=(10, 8)),
            selection=selection,
            fallback_reason="refinement_unavailable",
        )
    )

    assert result.selection_key == selection.selection_key
    assert result.mask is None
    assert result.metadata.refined is False
    assert result.metadata.fallback_reason == "refinement_inference_failed"


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf")])
def test_sam2_mask_candidate_rejects_invalid_quality_scores(score: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        Sam2MaskCandidate(mask=Image.new("L", (2, 2), 255), score=score)


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
        pixel = image.convert("RGB").getpixel((16, 12))
        assert isinstance(pixel, tuple)
        red, green, blue = pixel
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
    assert result.metadata.capability_alias == "deterministic_lasso_fallback"
    assert result.metadata.fallback_reason == "refinement_provider_unavailable"
