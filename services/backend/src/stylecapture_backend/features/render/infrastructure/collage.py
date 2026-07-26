from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.render.ports import CollageRenderError


@dataclass(frozen=True, slots=True)
class PillowLookCollageRenderer:
    canvas_width: int = 768
    canvas_height: int = 1024
    gap: int = 32
    padding: int = 48
    transparent_background: bool = False

    def render(self, images: Sequence[ImagePayload]) -> ImagePayload:
        if not images:
            raise CollageRenderError("collage requires at least one image")
        if len(images) > 6:
            raise CollageRenderError("collage supports at most six images")
        if self.canvas_width < 256 or self.canvas_height < 256:
            raise CollageRenderError("collage canvas dimensions must be at least 256 pixels")
        if self.padding < 0 or self.gap < 0:
            raise CollageRenderError("collage spacing must not be negative")
        mode = "RGBA"
        background = (255, 255, 255, 0) if self.transparent_background else (255, 255, 255, 255)
        canvas = Image.new(mode, (self.canvas_width, self.canvas_height), background)
        cells = _cells_for_count(
            len(images),
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
            padding=self.padding,
            gap=self.gap,
        )
        for image, cell in zip(images, cells, strict=True):
            source = _decode_image(image)
            fitted = ImageOps.contain(source, (cell.width, cell.height))
            shadow = Image.new("RGBA", fitted.size, (36, 24, 45, 32))
            shadow_position = (
                cell.x + (cell.width - fitted.width) // 2 + 8,
                cell.y + (cell.height - fitted.height) // 2 + 10,
            )
            canvas.alpha_composite(shadow, dest=shadow_position)
            position = (
                cell.x + (cell.width - fitted.width) // 2,
                cell.y + (cell.height - fitted.height) // 2,
            )
            canvas.alpha_composite(fitted, dest=position)
        buffer = BytesIO()
        canvas.save(buffer, format="PNG", optimize=False)
        body = buffer.getvalue()
        return ImagePayload(
            object_key="derived/renders/collage-pending.png",
            content_type="image/png",
            body=body,
            sha256=sha256(body).hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class _Cell:
    x: int
    y: int
    width: int
    height: int


def _decode_image(payload: ImagePayload) -> Image.Image:
    try:
        with Image.open(BytesIO(payload.body)) as image:
            decoded = ImageOps.exif_transpose(image).convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise CollageRenderError(
            f"collage input is not a readable image: {payload.object_key}"
        ) from error
    if decoded.width <= 0 or decoded.height <= 0:
        raise CollageRenderError(f"collage input has invalid dimensions: {payload.object_key}")
    return decoded


def _cells_for_count(
    count: int,
    *,
    canvas_width: int,
    canvas_height: int,
    padding: int,
    gap: int,
) -> tuple[_Cell, ...]:
    columns, rows = _grid_for_count(count)
    available_width = canvas_width - padding * 2 - gap * (columns - 1)
    available_height = canvas_height - padding * 2 - gap * (rows - 1)
    if available_width <= 0 or available_height <= 0:
        raise CollageRenderError("collage spacing leaves no drawable area")
    cell_width = available_width // columns
    cell_height = available_height // rows
    cells: list[_Cell] = []
    for index in range(count):
        row = index // columns
        column = index % columns
        cells.append(
            _Cell(
                x=padding + column * (cell_width + gap),
                y=padding + row * (cell_height + gap),
                width=cell_width,
                height=cell_height,
            )
        )
    return tuple(cells)


def _grid_for_count(count: int) -> tuple[int, int]:
    if count == 1:
        return 1, 1
    if count <= 4:
        return 2, 2
    return 3, 2
