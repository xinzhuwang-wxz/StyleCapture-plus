from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from PIL import Image, ImageChops, ImageFilter, ImageOps, UnidentifiedImageError

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.render.ports import CollageRenderError


@dataclass(frozen=True, slots=True)
class PillowLookCollageRenderer:
    canvas_size: int | None = None
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
        canvas_width = self.canvas_size or self.canvas_width
        canvas_height = self.canvas_size or self.canvas_height
        if canvas_width < 256 or canvas_height < 256:
            raise CollageRenderError("collage canvas dimensions must be at least 256 pixels")
        if self.padding < 0 or self.gap < 0:
            raise CollageRenderError("collage spacing must not be negative")
        mode = "RGBA"
        background = (255, 255, 255, 0) if self.transparent_background else (255, 255, 255, 255)
        canvas = Image.new(mode, (canvas_width, canvas_height), background)
        cells = _cells_for_count(
            len(images),
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            padding=self.padding,
            gap=self.gap,
        )
        for image, cell in zip(images, cells, strict=True):
            source = _decode_image(image, trim_near_white_edges=len(images) == 1)
            fitted = ImageOps.contain(source, (cell.width, cell.height))
            shadow_position = (
                cell.x + (cell.width - fitted.width) // 2 + 8,
                cell.y + (cell.height - fitted.height) // 2 + 10,
            )
            alpha = fitted.getchannel("A")
            if alpha.getextrema()[0] < 255:
                shadow = Image.new("RGBA", fitted.size, (36, 24, 45, 0))
                shadow.putalpha(
                    alpha.filter(ImageFilter.GaussianBlur(radius=6)).point(
                        lambda opacity: opacity * 32 // 255
                    )
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


def _decode_image(
    payload: ImagePayload,
    *,
    trim_near_white_edges: bool = False,
) -> Image.Image:
    try:
        with Image.open(BytesIO(payload.body)) as image:
            decoded = ImageOps.exif_transpose(image).convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise CollageRenderError(
            f"collage input is not a readable image: {payload.object_key}"
        ) from error
    if decoded.width <= 0 or decoded.height <= 0:
        raise CollageRenderError(f"collage input has invalid dimensions: {payload.object_key}")
    return _trim_item_edges(decoded) if trim_near_white_edges else decoded


def _trim_item_edges(image: Image.Image) -> Image.Image:
    """Remove baked-in empty framing without altering real garment pixels.

    Segmented assets normally carry transparency. Some compatible legacy display assets
    are opaque white product photos, so use a conservative near-white edge crop only
    when it finds a bounded foreground. Keeping a small inset preserves anti-aliased
    hems and shadows while removing UI-like right/bottom rules from the source asset.
    """
    alpha = image.getchannel("A")
    alpha_min, _alpha_max = alpha.getextrema()
    if alpha_min < 255:
        bbox = alpha.getbbox()
    else:
        red, green, blue, _ = image.split()
        foreground = ImageChops.lighter(
            ImageChops.lighter(
                red.point(lambda value: 255 if value < 245 else 0),
                green.point(lambda value: 255 if value < 245 else 0),
            ),
            blue.point(lambda value: 255 if value < 245 else 0),
        )
        bbox = foreground.getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    inset = 12
    left = max(0, left - inset)
    top = max(0, top - inset)
    right = min(image.width, right + inset)
    bottom = min(image.height, bottom + inset)
    if (left, top, right, bottom) == (0, 0, image.width, image.height):
        return image
    return image.crop((left, top, right, bottom))


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
