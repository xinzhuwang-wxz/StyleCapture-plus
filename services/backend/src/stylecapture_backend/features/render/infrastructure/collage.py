from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from math import ceil
from typing import cast

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
        if len(images) > 8:
            raise CollageRenderError("collage supports at most eight images")
        canvas_width = self.canvas_size or self.canvas_width
        canvas_height = self.canvas_size or self.canvas_height
        if canvas_width < 256 or canvas_height < 256:
            raise CollageRenderError("collage canvas dimensions must be at least 256 pixels")
        if self.padding < 0 or self.gap < 0:
            raise CollageRenderError("collage spacing must not be negative")
        mode = "RGBA"
        background = (255, 255, 255, 0) if self.transparent_background else (255, 255, 255, 255)
        canvas = Image.new(mode, (canvas_width, canvas_height), background)
        sources = [_decode_image(image, trim_near_white_edges=True) for image in images]
        cells = _cells_for_count(
            len(sources),
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            padding=self.padding,
            gap=self.gap,
        )
        for source, cell in zip(_visual_order(sources), cells, strict=True):
            fit_width = max(1, cell.width - 18)
            fit_height = max(1, cell.height - 22)
            fitted = ImageOps.contain(source, (fit_width, fit_height))
            shadow_position = (
                cell.x + (cell.width - fitted.width) // 2 + 8,
                cell.y + (cell.height - fitted.height) // 2 + 10,
            )
            alpha = fitted.getchannel("A")
            alpha_min, _alpha_max = cast(tuple[int, int], alpha.getextrema())
            if alpha_min < 255:
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
    if not trim_near_white_edges:
        return decoded
    return _remove_edge_background(_trim_item_edges(decoded))


def _trim_item_edges(image: Image.Image) -> Image.Image:
    """Remove baked-in empty framing without altering real garment pixels.

    Segmented assets normally carry transparency. Some compatible legacy display assets
    are opaque white product photos, so use a conservative near-white edge crop only
    when it finds a bounded foreground. Keeping a small inset preserves anti-aliased
    hems and shadows while removing UI-like right/bottom rules from the source asset.
    """
    alpha = image.getchannel("A")
    alpha_min, _alpha_max = cast(tuple[int, int], alpha.getextrema())
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


def _remove_edge_background(image: Image.Image) -> Image.Image:
    """Make only edge-connected near-white product-photo backgrounds transparent."""
    alpha = image.getchannel("A")
    alpha_min, _alpha_max = cast(tuple[int, int], alpha.getextrema())
    if alpha_min < 255:
        return image

    cleaned = image.copy()
    pixels = cleaned.load()
    if pixels is None:
        return cleaned
    width, height = cleaned.size
    seen = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def index(x: int, y: int) -> int:
        return y * width + x

    def is_background(x: int, y: int) -> bool:
        red, green, blue, opacity = cast(tuple[int, int, int, int], pixels[x, y])
        if opacity == 0:
            return False
        return min(red, green, blue) >= 225 and max(red, green, blue) - min(red, green, blue) <= 24

    def push(x: int, y: int) -> None:
        offset = index(x, y)
        if seen[offset] or not is_background(x, y):
            return
        seen[offset] = 1
        queue.append((x, y))

    for x in range(width):
        push(x, 0)
        push(x, height - 1)
    for y in range(1, height - 1):
        push(0, y)
        push(width - 1, y)

    while queue:
        x, y = queue.popleft()
        red, green, blue, _opacity = cast(tuple[int, int, int, int], pixels[x, y])
        pixels[x, y] = (red, green, blue, 0)
        if x > 0:
            push(x - 1, y)
        if x + 1 < width:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y + 1 < height:
            push(x, y + 1)

    return cleaned


def _cells_for_count(
    count: int,
    *,
    canvas_width: int,
    canvas_height: int,
    padding: int,
    gap: int,
) -> tuple[_Cell, ...]:
    square_size = min(canvas_width, canvas_height) - padding * 2
    available_width = square_size
    available_height = square_size
    padding_x = (canvas_width - square_size) // 2
    padding_y = (canvas_height - square_size) // 2
    if available_width <= 0 or available_height <= 0:
        raise CollageRenderError("collage spacing leaves no drawable area")
    if count == 1:
        return (_Cell(padding_x, padding_y, available_width, available_height),)

    if count == 2:
        cell_height = (available_height - gap) // 2
        if cell_height <= 0:
            raise CollageRenderError("collage spacing leaves no drawable area")
        return (
            _Cell(padding_x, padding_y, available_width, cell_height),
            _Cell(padding_x, padding_y + cell_height + gap, available_width, cell_height),
        )

    # Keep the two largest visual pieces as the outfit anchors, then arrange small
    # accessories in a compact right rail. This avoids a single garment swallowing
    # the canvas while preserving readable, uncropped product silhouettes.
    split_width = available_width - gap
    primary_width = int(split_width * 0.56)
    secondary_width = split_width - primary_width
    primary_rows = 2
    primary_cell_height = (available_height - gap) // primary_rows
    secondary_count = count - primary_rows
    secondary_columns = 1 if secondary_count == 1 else 2
    secondary_rows = ceil(secondary_count / secondary_columns)
    secondary_cell_width = (secondary_width - gap * (secondary_columns - 1)) // secondary_columns
    secondary_cell_height = (available_height - gap * (secondary_rows - 1)) // secondary_rows
    if (
        primary_width <= 0
        or primary_cell_height <= 0
        or secondary_width <= 0
        or secondary_cell_width <= 0
        or secondary_cell_height <= 0
    ):
        raise CollageRenderError("collage spacing leaves no drawable area")

    cells = [
        _Cell(
            padding_x,
            padding_y + row * (primary_cell_height + gap),
            primary_width,
            primary_cell_height,
        )
        for row in range(primary_rows)
    ]
    secondary_x = padding_x + primary_width + gap
    for index in range(secondary_count):
        row = index // secondary_columns
        column = index % secondary_columns
        cells.append(
            _Cell(
                x=secondary_x + column * (secondary_cell_width + gap),
                y=padding_y + row * (secondary_cell_height + gap),
                width=secondary_cell_width,
                height=secondary_cell_height,
            )
        )
    return tuple(cells)


def _visual_order(sources: Sequence[Image.Image]) -> tuple[Image.Image, ...]:
    if len(sources) < 4:
        return tuple(sources)
    return tuple(
        sorted(
            sources,
            key=lambda image: (image.width * image.height, max(image.width, image.height)),
            reverse=True,
        )
    )
