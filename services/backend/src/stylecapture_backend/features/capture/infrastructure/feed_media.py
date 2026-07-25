from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from secrets import token_hex
from threading import Lock
from time import perf_counter
from typing import Any, Protocol

from PIL import Image, ImageDraw, UnidentifiedImageError

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
SAM2_TINY_MODEL_ID = "facebook/sam2.1-hiera-tiny"
PROMPTABLE_SEGMENTATION_PROVIDER = "local_promptable_segmentation"
SEGMENTATION_MODEL_ALIAS = "segmentation_refinement"


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
                capability_alias="deterministic_lasso_fallback",
                representation=SegmentationRepresentation.COARSE_POLYGON,
                refined=False,
                schema_version=SEGMENTATION_SCHEMA_VERSION,
                latency_ms=0,
                fallback_reason=prompt.fallback_reason,
            ),
        )


@dataclass(frozen=True, slots=True)
class Sam2MaskCandidate:
    mask: Image.Image
    score: float

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 1:
            raise ValueError("SAM2 mask score must be between 0 and 1")


class Sam2SegmentationBackend(Protocol):
    def segment_box(
        self,
        image: Image.Image,
        box: tuple[int, int, int, int],
    ) -> Sequence[Sam2MaskCandidate]: ...


class Sam2PromptableSegmentationProvider:
    def __init__(
        self,
        *,
        backend_factory: Callable[[], Sam2SegmentationBackend] | None = None,
        model: str = SAM2_TINY_MODEL_ID,
        model_alias: str = SEGMENTATION_MODEL_ALIAS,
        device: str = "cpu",
        score_threshold: float = 0.7,
        fallback: CoarsePolygonSegmentationProvider | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("SAM2 model must not be empty")
        if not model_alias.strip():
            raise ValueError("SAM2 model alias must not be empty")
        if not 0 <= score_threshold <= 1:
            raise ValueError("SAM2 score threshold must be between 0 and 1")
        self._backend_factory = backend_factory or (
            lambda: TransformersSam2Backend(model=model, device=device)
        )
        self._backend: Sam2SegmentationBackend | None = None
        self._load_lock = Lock()
        self._model_alias = model_alias
        self._score_threshold = score_threshold
        self._fallback = fallback or CoarsePolygonSegmentationProvider()

    def segment(self, prompt: SegmentationPrompt) -> SegmentationResult:
        started = perf_counter()
        try:
            with Image.open(BytesIO(prompt.frame.body)) as source:
                image = source.convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError):
            return self._fallback_result(prompt, "refinement_frame_invalid")
        box = _selection_pixel_box(prompt.selection.polygon, image.size)
        try:
            candidates = tuple(self._backend_instance().segment_box(image, box))
        except Exception:
            reason = (
                "refinement_model_unavailable"
                if self._backend is None
                else "refinement_inference_failed"
            )
            return self._fallback_result(prompt, reason)

        non_empty = tuple(
            candidate for candidate in candidates if candidate.mask.getbbox() is not None
        )
        if not non_empty:
            reason = "refinement_model_unavailable" if not candidates else "refinement_empty_mask"
            return self._fallback_result(prompt, reason)
        best = max(non_empty, key=lambda candidate: candidate.score)
        if best.score < self._score_threshold:
            return self._fallback_result(prompt, "refinement_low_score")
        try:
            mask = best.mask.convert("L")
            if mask.size != image.size:
                mask = mask.resize(image.size, Image.Resampling.NEAREST)
            output = BytesIO()
            mask.save(output, format="PNG", optimize=True)
        except (OSError, ValueError):
            return self._fallback_result(prompt, "refinement_mask_malformed")

        body = output.getvalue()
        return SegmentationResult(
            selection_key=prompt.selection.selection_key,
            coarse_polygon=prompt.selection.polygon,
            mask=ImagePayload(
                object_key=f"{prompt.frame.object_key}#mask={prompt.selection.selection_key}",
                content_type="image/png",
                body=body,
                sha256=sha256(body).hexdigest(),
            ),
            metadata=SegmentationMetadata(
                capability_alias=PROMPTABLE_SEGMENTATION_PROVIDER,
                representation=SegmentationRepresentation.REFINED_MASK,
                refined=True,
                schema_version=SEGMENTATION_SCHEMA_VERSION,
                latency_ms=round((perf_counter() - started) * 1000),
                model_alias=self._model_alias,
                score=best.score,
            ),
        )

    def _backend_instance(self) -> Sam2SegmentationBackend:
        if self._backend is not None:
            return self._backend
        with self._load_lock:
            if self._backend is None:
                self._backend = self._backend_factory()
        return self._backend

    def _fallback_result(self, prompt: SegmentationPrompt, reason: str) -> SegmentationResult:
        return self._fallback.segment(
            SegmentationPrompt(
                frame=prompt.frame,
                selection=prompt.selection,
                fallback_reason=reason,
            )
        )


class TransformersSam2Backend:
    def __init__(self, *, model: str = SAM2_TINY_MODEL_ID, device: str = "cpu") -> None:
        import torch  # type: ignore[import-not-found,unused-ignore]
        from transformers import (  # type: ignore[import-not-found,unused-ignore]
            Sam2Model,
            Sam2Processor,
        )

        self._torch = torch
        self._processor = Sam2Processor.from_pretrained(model)
        self._model = Sam2Model.from_pretrained(
            model,
            use_safetensors=True,
        ).to(device)
        self._model.eval()
        self._device = device

    def segment_box(
        self,
        image: Image.Image,
        box: tuple[int, int, int, int],
    ) -> tuple[Sam2MaskCandidate, ...]:
        inputs = self._processor(
            images=image,
            input_boxes=[[list(box)]],
            return_tensors="pt",
        ).to(self._device)
        with self._torch.inference_mode():
            outputs = self._model(**inputs)
        masks = self._processor.post_process_masks(
            outputs.pred_masks.cpu(),
            inputs["original_sizes"].cpu(),
        )[0][0]
        scores = outputs.iou_scores[0][0].float().detach().cpu().tolist()
        return tuple(
            Sam2MaskCandidate(mask=_tensor_mask_to_image(mask), score=float(score))
            for mask, score in zip(masks, scores, strict=False)
        )


class PillowSelectionImageRenderer:
    def render(
        self,
        frame: ImagePayload,
        segmentation: SegmentationResult,
    ) -> ImagePayload:
        try:
            with Image.open(BytesIO(frame.body)) as source:
                rendered = source.convert("RGBA")
            alpha = self._alpha_mask(rendered.size, segmentation)
            rendered.putalpha(alpha)
            bounds = alpha.getbbox()
            if bounds is None:
                raise ValueError("selection mask is empty")
            selected = rendered.crop(bounds)
            output = BytesIO()
            selected.save(output, format="PNG", optimize=True)
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise ProviderError(
                "selection_image_invalid",
                "The selected Feed pixels could not be prepared",
                retryable=False,
            ) from error
        body = output.getvalue()
        return ImagePayload(
            object_key=f"{frame.object_key}#selection={segmentation.selection_key}",
            content_type="image/png",
            body=body,
            sha256=sha256(body).hexdigest(),
        )

    @staticmethod
    def _alpha_mask(
        size: tuple[int, int],
        segmentation: SegmentationResult,
    ) -> Image.Image:
        width, height = size
        if segmentation.mask is not None:
            try:
                with Image.open(BytesIO(segmentation.mask.body)) as source:
                    mask = source.convert("L")
            except (UnidentifiedImageError, OSError, ValueError) as error:
                raise ValueError("refined selection mask is invalid") from error
            if mask.size != size:
                mask = mask.resize(size, Image.Resampling.NEAREST)
            return mask
        mask = Image.new("L", size, 0)
        points = [
            (
                min(width - 1, max(0, round(point.x * (width - 1)))),
                min(height - 1, max(0, round(point.y * (height - 1)))),
            )
            for point in segmentation.coarse_polygon
        ]
        ImageDraw.Draw(mask).polygon(points, fill=255)
        return mask


def _selection_pixel_box(
    polygon: tuple[Any, ...],
    size: tuple[int, int],
) -> tuple[int, int, int, int]:
    width, height = size
    x_values = [point.x for point in polygon]
    y_values = [point.y for point in polygon]
    return (
        _normalized_to_pixel(min(x_values), width),
        _normalized_to_pixel(min(y_values), height),
        _normalized_to_pixel(max(x_values), width),
        _normalized_to_pixel(max(y_values), height),
    )


def _normalized_to_pixel(value: float, length: int) -> int:
    return min(length - 1, max(0, round(value * (length - 1))))


def _tensor_mask_to_image(mask: Any) -> Image.Image:
    values = mask.detach().cpu() > 0
    height, width = values.shape[-2:]
    packed = bytes(255 if bool(value) else 0 for value in values.reshape(-1).tolist())
    return Image.frombytes("L", (width, height), packed)
