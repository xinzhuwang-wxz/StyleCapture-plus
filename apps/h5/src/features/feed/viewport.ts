export interface ViewportSize {
  width: number;
  height: number;
}

export interface ViewportPoint {
  x: number;
  y: number;
}

export interface VideoContentBox extends ViewportSize, ViewportPoint {}

const clampUnit = (value: number) => Math.min(Math.max(value, 0), 1);
const hasPositiveFiniteDimensions = (size: ViewportSize) =>
  Number.isFinite(size.width) &&
  Number.isFinite(size.height) &&
  size.width > 0 &&
  size.height > 0;

/**
 * Returns the rendered video pixels inside an `object-fit: contain` element.
 * Adapted from the audited Video Branch `VideoScreen` viewport calculation.
 */
export function contentBoxForContainedVideo(
  element: ViewportSize,
  intrinsicVideo: ViewportSize
): VideoContentBox | null {
  if (
    !hasPositiveFiniteDimensions(element) ||
    !hasPositiveFiniteDimensions(intrinsicVideo)
  ) {
    return null;
  }

  const scale = Math.min(
    element.width / intrinsicVideo.width,
    element.height / intrinsicVideo.height
  );
  const width = intrinsicVideo.width * scale;
  const height = intrinsicVideo.height * scale;

  return {
    x: (element.width - width) / 2,
    y: (element.height - height) / 2,
    width,
    height
  };
}

export function normalizePointToVideo(
  point: ViewportPoint,
  contentBox: VideoContentBox
): ViewportPoint {
  return {
    x: clampUnit((point.x - contentBox.x) / contentBox.width),
    y: clampUnit((point.y - contentBox.y) / contentBox.height)
  };
}

export function denormalizeVideoPoint(
  point: ViewportPoint,
  contentBox: VideoContentBox
): ViewportPoint {
  return {
    x: contentBox.x + point.x * contentBox.width,
    y: contentBox.y + point.y * contentBox.height
  };
}
