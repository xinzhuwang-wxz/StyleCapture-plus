export type PixelSceneFrame = {
  elapsed: number;
  delta: number;
};

export type PixelSceneRenderer = (
  context: CanvasRenderingContext2D,
  frame: PixelSceneFrame
) => void;

/**
 * Thin adaptation of Pixel Agents' Canvas game loop.
 * Source: pixel-agents-hq/pixel-agents@f6cdd2d37e203f4df8a7341e93b35df6d47b5fb5
 * License: MIT
 */
export function startPixelSceneLoop(
  canvas: HTMLCanvasElement,
  render: PixelSceneRenderer
): () => void {
  const context = canvas.getContext("2d");
  if (!context) return () => undefined;

  context.imageSmoothingEnabled = false;
  let animationFrame = 0;
  let previousTime = 0;
  let elapsed = 0;
  let stopped = false;

  const frame = (time: number) => {
    if (stopped) return;
    const delta =
      previousTime === 0 ? 0 : Math.min((time - previousTime) / 1_000, 0.1);
    previousTime = time;
    elapsed += delta;
    context.imageSmoothingEnabled = false;
    render(context, { elapsed, delta });
    animationFrame = window.requestAnimationFrame(frame);
  };

  animationFrame = window.requestAnimationFrame(frame);
  return () => {
    stopped = true;
    window.cancelAnimationFrame(animationFrame);
  };
}
