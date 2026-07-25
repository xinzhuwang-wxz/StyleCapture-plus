import {
  normalizePointToVideo,
  type VideoContentBox,
  type ViewportPoint
} from "./viewport";

export function closeNormalizedLasso(
  elementPoints: readonly ViewportPoint[],
  contentBox: VideoContentBox
): ViewportPoint[] {
  const normalized = elementPoints.map((point) =>
    normalizePointToVideo(point, contentBox)
  );

  if (normalized.length === 0) {
    return [];
  }

  const first = normalized[0];
  const last = normalized.at(-1);
  return last?.x === first.x && last.y === first.y
    ? normalized
    : [...normalized, first];
}
