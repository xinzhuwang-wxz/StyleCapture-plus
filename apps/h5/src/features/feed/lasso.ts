import {
  normalizePointToVideo,
  type VideoContentBox,
  type ViewportPoint
} from "./viewport";

export function closeNormalizedLasso(
  elementPoints: readonly ViewportPoint[],
  contentBox: VideoContentBox
): ViewportPoint[] | null {
  const normalized = elementPoints.map((point) =>
    normalizePointToVideo(point, contentBox)
  );

  const uniquePoints = new Set(
    normalized.map((point) => `${point.x}:${point.y}`)
  );
  if (uniquePoints.size < 3) {
    return null;
  }

  const first = normalized[0];
  const last = normalized.at(-1);
  return last?.x === first.x && last.y === first.y
    ? normalized
    : [...normalized, first];
}
