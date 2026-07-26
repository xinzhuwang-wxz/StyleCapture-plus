import {
  normalizePointToVideo,
  type VideoContentBox,
  type ViewportPoint
} from "./viewport";

const MIN_LASSO_EXTENT_RATIO = 0.04;

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

  const xs = normalized.map((point) => point.x);
  const ys = normalized.map((point) => point.y);
  const width = Math.max(...xs) - Math.min(...xs);
  const height = Math.max(...ys) - Math.min(...ys);
  if (width < MIN_LASSO_EXTENT_RATIO || height < MIN_LASSO_EXTENT_RATIO) {
    return null;
  }

  const first = normalized[0];
  const last = normalized.at(-1);
  return last?.x === first.x && last.y === first.y
    ? normalized
    : [...normalized, first];
}
