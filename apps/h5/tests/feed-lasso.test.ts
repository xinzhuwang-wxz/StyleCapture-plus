import { closeNormalizedLasso } from "../src/features/feed/lasso";

describe("Feed lasso normalization", () => {
  it("closes a drawn loop in normalized video-content coordinates", () => {
    const closed = closeNormalizedLasso(
      [
        { x: 100, y: 120 },
        { x: 300, y: 120 },
        { x: 300, y: 280 },
        { x: 100, y: 280 }
      ],
      { x: 0, y: 100, width: 400, height: 200 }
    );

    expect(closed).not.toBeNull();
    expect(closed).toEqual([
      { x: 0.25, y: 0.1 },
      { x: 0.75, y: 0.1 },
      { x: 0.75, y: 0.9 },
      { x: 0.25, y: 0.9 },
      { x: 0.25, y: 0.1 }
    ]);
  });

  it("does not append a second closure point when the pointer already returned to start", () => {
    const closed = closeNormalizedLasso(
      [
        { x: 10, y: 10 },
        { x: 90, y: 10 },
        { x: 90, y: 90 },
        { x: 10, y: 10 }
      ],
      { x: 0, y: 0, width: 100, height: 100 }
    );

    expect(closed).not.toBeNull();
    if (!closed) {
      throw new Error("expected a valid closed lasso");
    }
    expect(closed).toHaveLength(4);
    expect(closed.at(-1)).toEqual({ x: 0.1, y: 0.1 });
  });

  it("discards a tap or clamped path with fewer than three unique video points", () => {
    expect(
      closeNormalizedLasso(
        [
          { x: 20, y: 20 },
          { x: 20, y: 20 }
        ],
        { x: 0, y: 0, width: 100, height: 100 }
      )
    ).toBeNull();
    expect(
      closeNormalizedLasso(
        [
          { x: -20, y: -20 },
          { x: -10, y: -10 },
          { x: -5, y: -5 }
        ],
        { x: 0, y: 0, width: 100, height: 100 }
      )
    ).toBeNull();
  });
});
