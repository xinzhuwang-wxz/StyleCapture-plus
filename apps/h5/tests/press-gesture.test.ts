import {
  LONG_PRESS_MS,
  MOVE_TOLERANCE,
  idlePress,
  pressDown,
  pressHeld,
  pressMove,
  pressUp
} from "../src/features/combo/pressGesture";

/**
 * 这三条分支在真机上最容易互相串，所以每条都单独钉死。
 */
describe("press gesture", () => {
  it("treats a quick tap that stays put as a click", () => {
    let state = pressDown(100, 100, 0);
    state = pressMove(state, 102, 101, 60);
    const { outcome } = pressUp(state, 120);
    expect(outcome).toBe("click");
  });

  it("treats an early drift as list scrolling, not a click or a drag", () => {
    let state = pressDown(100, 100, 0);
    state = pressMove(state, 100, 100 + MOVE_TOLERANCE + 5, 80);
    expect(state.phase).toBe("abandoned");
    // Crucially it must not become a click either — the user was scrolling.
    expect(pressUp(state, 200).outcome).toBe("none");
  });

  it("starts a drag only after the hold time with the finger still", () => {
    let state = pressDown(100, 100, 0);
    state = pressMove(state, 103, 102, 200);
    expect(state.phase).toBe("pressing");

    state = pressHeld(state, LONG_PRESS_MS - 1);
    expect(state.phase).toBe("pressing");

    state = pressHeld(state, LONG_PRESS_MS);
    expect(state.phase).toBe("dragging");
  });

  it("will not start a drag if the finger wandered while holding", () => {
    let state = pressDown(100, 100, 0);
    state = pressMove(state, 100, 105, 100);
    state = pressMove(state, 100, 140, 200); // scrolled away
    expect(state.phase).toBe("abandoned");
    expect(pressHeld(state, LONG_PRESS_MS + 50).phase).toBe("abandoned");
  });

  it("keeps dragging once started, even when the finger moves far", () => {
    let state = pressDown(100, 100, 0);
    state = pressHeld(state, LONG_PRESS_MS);
    state = pressMove(state, 300, 500, LONG_PRESS_MS + 100);
    expect(state.phase).toBe("dragging");
    expect(state).toMatchObject({ x: 300, y: 500 });
    expect(pressUp(state, LONG_PRESS_MS + 200).outcome).toBe("drop");
  });

  it("promotes a long hold to a drag when the finger finally moves", () => {
    // Held long enough, then moved: that is a drag, not a scroll.
    let state = pressDown(100, 100, 0);
    state = pressMove(state, 100, 160, LONG_PRESS_MS + 10);
    expect(state.phase).toBe("dragging");
  });

  it("a slow release without a drag is neither click nor drop", () => {
    const state = pressDown(100, 100, 0);
    expect(pressUp(state, LONG_PRESS_MS + 100).outcome).toBe("none");
  });

  it("ignores movement when no press is in progress", () => {
    const state = idlePress();
    expect(pressMove(state, 10, 10, 5)).toBe(state);
    expect(pressUp(state, 5).outcome).toBe("none");
  });
});
