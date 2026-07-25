import {
  beginSelectionLoop,
  completeSelectionLoop,
  createSelectionSession,
  settleSelectionSession
} from "../src/features/feed/selectionSession";

const frame = {
  videoId: "pexels-19862866",
  timestampMs: 2400
};

describe("Feed same-frame selection session", () => {
  it("keeps consecutive loops together and restarts settling after the newest loop", () => {
    const firstDrawing = beginSelectionLoop(createSelectionSession(), frame);
    const afterFirst = completeSelectionLoop(
      firstDrawing,
      {
        id: "selection-1",
        path: [
          { x: 0.1, y: 0.1 },
          { x: 0.4, y: 0.1 },
          { x: 0.4, y: 0.4 },
          { x: 0.1, y: 0.1 }
        ]
      },
      1000
    );

    expect(afterFirst.settleAtMs).toBe(1700);

    const secondDrawing = beginSelectionLoop(afterFirst, frame);
    expect(secondDrawing.settleAtMs).toBeNull();
    expect(secondDrawing.selections).toHaveLength(1);

    const afterSecond = completeSelectionLoop(
      secondDrawing,
      {
        id: "selection-2",
        path: [
          { x: 0.5, y: 0.5 },
          { x: 0.9, y: 0.5 },
          { x: 0.9, y: 0.9 },
          { x: 0.5, y: 0.5 }
        ]
      },
      1300
    );

    expect(afterSecond).toMatchObject({
      phase: "collecting",
      frame,
      settleAtMs: 2000
    });
    expect(afterSecond.selections.map((selection) => selection.id)).toEqual([
      "selection-1",
      "selection-2"
    ]);
  });

  it("settles only after the full 700ms quiet window", () => {
    const collecting = completeSelectionLoop(
      beginSelectionLoop(createSelectionSession(), frame),
      {
        id: "selection-1",
        path: [
          { x: 0.1, y: 0.1 },
          { x: 0.4, y: 0.1 },
          { x: 0.4, y: 0.4 },
          { x: 0.1, y: 0.1 }
        ]
      },
      1000
    );

    expect(settleSelectionSession(collecting, 1699).phase).toBe("collecting");
    expect(settleSelectionSession(collecting, 1700)).toMatchObject({
      phase: "settled",
      settleAtMs: null,
      frame
    });
  });
});
