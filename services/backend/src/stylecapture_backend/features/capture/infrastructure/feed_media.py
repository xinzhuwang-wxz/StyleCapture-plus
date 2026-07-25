from __future__ import annotations

import shutil
import subprocess
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from secrets import token_hex

from PIL import Image, UnidentifiedImageError

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.capture.feed_media import (
    ExtractFrameRequest,
    SegmentationMetadata,
    SegmentationPrompt,
    SegmentationRepresentation,
    SegmentationResult,
)
from stylecapture_backend.features.capture.processing import ProviderError

SEGMENTATION_SCHEMA_VERSION = "feed-segmentation-v1"


class FfmpegFrameExtractor:
    def __init__(
        self,
        *,
        source_root: Path,
        frame_root: Path,
        ffmpeg_binary: str | None = None,
        timeout_seconds: float = 15,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("FFmpeg timeout must be positive")
        self._source_root = source_root.resolve()
        self._frame_root = frame_root.resolve()
        self._ffmpeg_binary = ffmpeg_binary or shutil.which("ffmpeg")
        self._timeout_seconds = timeout_seconds

    def extract(self, request: ExtractFrameRequest) -> ImagePayload:
        source_path = self._source_path(request.source_object_key)
        frame_path = self._frame_path(request.frame_object_key)
        if self._ffmpeg_binary is None:
            raise ProviderError(
                "media_extractor_unavailable",
                "FFmpeg is not installed in the media worker",
                retryable=False,
            )
        try:
            frame_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ProviderError(
                "media_frame_storage_unavailable",
                "The extracted frame storage is unavailable",
                retryable=True,
            ) from error
        temporary_path = frame_path.with_name(
            f"{frame_path.stem}.extracting-{token_hex(8)}{frame_path.suffix}"
        )
        try:
            try:
                completed = subprocess.run(
                    [
                        self._ffmpeg_binary,
                        "-nostdin",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(source_path),
                        "-ss",
                        f"{request.timestamp_ms / 1000:.3f}",
                        "-frames:v",
                        "1",
                        "-map_metadata",
                        "-1",
                        "-threads",
                        "1",
                        "-f",
                        "image2",
                        "-c:v",
                        "png",
                        "-y",
                        str(temporary_path),
                    ],
                    capture_output=True,
                    check=False,
                    stdin=subprocess.DEVNULL,
                    timeout=self._timeout_seconds,
                )
            except subprocess.TimeoutExpired as error:
                raise ProviderError(
                    "media_extraction_timeout",
                    "Video frame extraction exceeded its time limit",
                    retryable=True,
                ) from error
            except FileNotFoundError as error:
                raise ProviderError(
                    "media_extractor_unavailable",
                    "FFmpeg is not installed in the media worker",
                    retryable=False,
                ) from error
            if completed.returncode != 0 or not temporary_path.is_file():
                raise ProviderError(
                    "media_extraction_failed",
                    "FFmpeg could not decode the requested video frame",
                    retryable=False,
                )
            try:
                body = temporary_path.read_bytes()
                self._validate_png(body)
                temporary_path.replace(frame_path)
            except ProviderError:
                raise
            except OSError as error:
                raise ProviderError(
                    "media_frame_storage_unavailable",
                    "The extracted frame could not be published",
                    retryable=True,
                ) from error
        finally:
            temporary_path.unlink(missing_ok=True)

        return ImagePayload(
            object_key=request.frame_object_key,
            content_type="image/png",
            body=body,
            sha256=sha256(body).hexdigest(),
        )

    def _source_path(self, object_key: str) -> Path:
        source_path = self._contained_path(
            self._source_root,
            object_key,
            invalid_code="media_source_invalid",
            invalid_message="The source video object key is invalid",
        )
        if not source_path.is_file():
            raise ProviderError(
                "media_source_invalid",
                "The persisted source video is unavailable",
                retryable=False,
            )
        return source_path

    def _frame_path(self, object_key: str) -> Path:
        if PurePosixPath(object_key).suffix.lower() != ".png":
            raise ProviderError(
                "media_frame_key_invalid",
                "Extracted Feed frames must use a PNG object key",
                retryable=False,
            )
        return self._contained_path(
            self._frame_root,
            object_key,
            invalid_code="media_frame_key_invalid",
            invalid_message="The extracted frame object key is invalid",
        )

    @staticmethod
    def _contained_path(
        root: Path,
        object_key: str,
        *,
        invalid_code: str,
        invalid_message: str,
    ) -> Path:
        logical_path = PurePosixPath(object_key)
        if (
            not object_key
            or logical_path.is_absolute()
            or ".." in logical_path.parts
            or "\\" in object_key
        ):
            raise ProviderError(
                invalid_code,
                invalid_message,
                retryable=False,
            )
        try:
            candidate = (root / object_key).resolve()
        except (OSError, ValueError) as error:
            raise ProviderError(
                invalid_code,
                invalid_message,
                retryable=False,
            ) from error
        if not candidate.is_relative_to(root):
            raise ProviderError(
                invalid_code,
                invalid_message,
                retryable=False,
            )
        return candidate

    @staticmethod
    def _validate_png(body: bytes) -> None:
        if not body.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ProviderError(
                "media_frame_invalid",
                "FFmpeg did not produce a valid PNG frame",
                retryable=False,
            )
        try:
            with Image.open(BytesIO(body)) as frame:
                if frame.format != "PNG" or frame.width <= 0 or frame.height <= 0:
                    raise ValueError("invalid PNG dimensions")
                frame.verify()
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise ProviderError(
                "media_frame_invalid",
                "FFmpeg did not produce a valid PNG frame",
                retryable=False,
            ) from error


class CoarsePolygonSegmentationProvider:
    def segment(self, prompt: SegmentationPrompt) -> SegmentationResult:
        return SegmentationResult(
            selection_key=prompt.selection.selection_key,
            coarse_polygon=prompt.selection.polygon,
            mask=None,
            metadata=SegmentationMetadata(
                provider="deterministic_lasso_fallback",
                representation=SegmentationRepresentation.COARSE_POLYGON,
                refined=False,
                schema_version=SEGMENTATION_SCHEMA_VERSION,
                latency_ms=0,
                fallback_reason=prompt.fallback_reason,
            ),
        )
