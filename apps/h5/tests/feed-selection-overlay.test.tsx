import { act, fireEvent, render, screen } from "@testing-library/react";

import { FeedSelectionOverlay } from "../src/features/feed/FeedSelectionOverlay";

class BrowserLikePointerEvent extends MouseEvent {
  readonly pointerId: number;

  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 0;
  }
}

function firePointer(
  target: HTMLElement,
  type: "pointerdown" | "pointermove" | "pointerup" | "pointercancel",
  init: PointerEventInit
) {
  fireEvent(
    target,
    new BrowserLikePointerEvent(type, {
      bubbles: true,
      cancelable: true,
      ...init
    })
  );
}

const frame = {
  videoId: "pexels-19862866",
  timestampMs: 2400
};

const stageRect = {
  x: 0,
  y: 0,
  top: 0,
  left: 0,
  right: 400,
  bottom: 800,
  width: 400,
  height: 800,
  toJSON: () => ({})
};

function drawLoop(
  overlay: HTMLElement,
  pointerId: number,
  points: ReadonlyArray<{ x: number; y: number }>
) {
  const [first, ...rest] = points;
  firePointer(overlay, "pointerdown", {
    pointerId,
    clientX: first.x,
    clientY: first.y
  });
  rest.forEach((point) =>
    firePointer(overlay, "pointermove", {
      pointerId,
      clientX: point.x,
      clientY: point.y
    })
  );
  const last = points.at(-1)!;
  firePointer(overlay, "pointerup", {
    pointerId,
    clientX: last.x,
    clientY: last.y
  });
}

function renderOverlay(options?: {
  gestureGuideToken?: number;
}) {
  const onConfirm = vi.fn();
  const onDismiss = vi.fn();
  const onEmptyTap = vi.fn();
  const view = render(
    <FeedSelectionOverlay
      frame={frame}
      frameImageUrl="blob:current-feed-frame"
      gestureGuideToken={options?.gestureGuideToken}
      videoSize={{ width: 1080, height: 2160 }}
      onConfirm={onConfirm}
      onDismiss={onDismiss}
      onEmptyTap={onEmptyTap}
    />
  );
  const overlay = screen.getByRole("application", { name: "圈选穿搭" });
  vi.spyOn(overlay, "getBoundingClientRect").mockReturnValue(stageRect);
  return { onConfirm, onDismiss, onEmptyTap, overlay, view };
}

describe("FeedSelectionOverlay", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-25T00:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("lifts all same-frame loops 700ms after the most recent loop", () => {
    const { overlay } = renderOverlay();

    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 160, y: 80 },
      { x: 160, y: 260 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(600));
    drawLoop(overlay, 2, [
      { x: 220, y: 360 },
      { x: 360, y: 360 },
      { x: 360, y: 620 },
      { x: 220, y: 360 }
    ]);

    act(() => vi.advanceTimersByTime(699));
    expect(
      screen.queryByRole("group", { name: "已圈选的穿搭主体" })
    ).not.toBeInTheDocument();

    act(() => vi.advanceTimersByTime(1));
    expect(
      screen.getByRole("group", { name: "已圈选的穿搭主体" })
    ).toHaveAttribute("data-selection-count", "2");
  });

  it("shows a live colorful trail and lifts pixels from the supplied frame", () => {
    const { overlay } = renderOverlay();

    firePointer(overlay, "pointerdown", {
      pointerId: 1,
      clientX: 40,
      clientY: 80
    });
    firePointer(overlay, "pointermove", {
      pointerId: 1,
      clientX: 160,
      clientY: 80
    });
    firePointer(overlay, "pointermove", {
      pointerId: 1,
      clientX: 160,
      clientY: 260
    });

    expect(
      screen.getByRole("img", { name: "正在圈选的炫彩轮廓" })
    ).toBeInTheDocument();

    firePointer(overlay, "pointerup", {
      pointerId: 1,
      clientX: 40,
      clientY: 80
    });
    act(() => vi.advanceTimersByTime(700));

    const liftedFrame = screen.getByRole("img", {
      name: "当前帧中已圈选的穿搭"
    });
    expect(liftedFrame).toHaveAttribute("href", "blob:current-feed-frame");
    expect(
      screen.queryByRole("img", { name: "正在圈选的炫彩轮廓" })
    ).not.toBeInTheDocument();
  });

  it("confirms the real same-frame selections when the lifted subject is swiped right", () => {
    const { onConfirm, onDismiss, overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 160, y: 80 },
      { x: 160, y: 260 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    const lifted = screen.getByRole("group", {
      name: "已圈选的穿搭主体"
    });
    firePointer(lifted, "pointerdown", {
      pointerId: 4,
      clientX: 180,
      clientY: 400
    });
    firePointer(lifted, "pointermove", {
      pointerId: 4,
      clientX: 300,
      clientY: 400
    });
    firePointer(lifted, "pointerup", {
      pointerId: 4,
      clientX: 300,
      clientY: 400
    });

    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onConfirm).toHaveBeenCalledWith({
      frame,
      intent: "whole_outfit",
      selections: [
        expect.objectContaining({
          id: "selection-1",
          path: expect.any(Array)
        })
      ]
    });
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("saves one loop as a whole outfit when the user chooses the outfit intent", () => {
    const { onConfirm, overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 360, y: 80 },
      { x: 360, y: 700 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    fireEvent.click(screen.getByRole("button", { name: "存整套" }));
    fireEvent.click(
      screen.getByRole("button", { name: "保存整套到数字衣橱" })
    );

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ intent: "whole_outfit" })
    );
  });

  it("defaults one lifted outfit selection to saving the whole look", () => {
    const { onConfirm, overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 360, y: 80 },
      { x: 360, y: 700 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    expect(screen.getByRole("button", { name: "存整套" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    fireEvent.click(
      screen.getByRole("button", { name: "保存整套到数字衣橱" })
    );

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ intent: "whole_outfit" })
    );
  });

  it("lifts the whole frame before a keyboard-accessible save decision", () => {
    const { onConfirm } = renderOverlay();

    fireEvent.click(
      screen.getByRole("button", { name: "一键保存整套穿搭" })
    );

    expect(onConfirm).not.toHaveBeenCalled();
    const lifted = screen.getByRole("group", {
      name: "已圈选的穿搭主体"
    });
    expect(lifted).toHaveAttribute("data-selection-count", "1");

    fireEvent.keyDown(lifted, { key: "ArrowRight" });

    expect(onConfirm).toHaveBeenCalledWith({
      frame,
      intent: "whole_outfit",
      selections: [
        {
          id: "whole-outfit-full-frame",
          path: [
            { x: 0, y: 0 },
            { x: 1, y: 0 },
            { x: 1, y: 1 },
            { x: 0, y: 1 }
          ]
        }
      ]
    });
  });

  it("lets the user reject a lifted whole-frame shortcut without writing", () => {
    const { onConfirm, onDismiss } = renderOverlay();

    fireEvent.click(
      screen.getByRole("button", { name: "一键保存整套穿搭" })
    );
    fireEvent.keyDown(
      screen.getByRole("group", { name: "已圈选的穿搭主体" }),
      { key: "ArrowLeft" }
    );

    expect(onConfirm).not.toHaveBeenCalled();
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("returns a settled selection to drawing so more items can be added", () => {
    const { overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 160, y: 80 },
      { x: 160, y: 260 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    fireEvent.click(screen.getByRole("button", { name: "继续圈选" }));
    expect(
      screen.queryByRole("group", { name: "已圈选的穿搭主体" })
    ).not.toBeInTheDocument();

    drawLoop(overlay, 2, [
      { x: 220, y: 360 },
      { x: 360, y: 360 },
      { x: 360, y: 620 },
      { x: 220, y: 360 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    expect(
      screen.getByRole("group", { name: "已圈选的穿搭主体" })
    ).toHaveAttribute("data-selection-count", "2");
  });

  it("exposes the selected save intent to assistive technology", () => {
    const { overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 360, y: 80 },
      { x: 360, y: 700 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    const itemIntent = screen.getByRole("button", { name: "存单品" });
    const outfitIntent = screen.getByRole("button", { name: "存整套" });
    expect(itemIntent).toHaveAttribute("aria-pressed", "false");
    expect(outfitIntent).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(itemIntent);
    expect(itemIntent).toHaveAttribute("aria-pressed", "true");
    expect(outfitIntent).toHaveAttribute("aria-pressed", "false");
  });

  it("dismisses without a write when the lifted subject is swiped left", () => {
    const { onConfirm, onDismiss, overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 160, y: 80 },
      { x: 160, y: 260 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    const lifted = screen.getByRole("group", {
      name: "已圈选的穿搭主体"
    });
    firePointer(lifted, "pointerdown", {
      pointerId: 5,
      clientX: 220,
      clientY: 400
    });
    firePointer(lifted, "pointermove", {
      pointerId: 5,
      clientX: 100,
      clientY: 400
    });
    firePointer(lifted, "pointerup", {
      pointerId: 5,
      clientX: 100,
      clientY: 400
    });

    expect(onDismiss).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("group", { name: "已圈选的穿搭主体" })
    ).not.toBeInTheDocument();
  });

  it("offers button equivalents for both swipe decisions", () => {
    const { onConfirm, onDismiss, overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 160, y: 80 },
      { x: 160, y: 260 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    fireEvent.click(
      screen.getByRole("button", { name: "保存整套到数字衣橱" })
    );
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onDismiss).not.toHaveBeenCalled();

    drawLoop(overlay, 2, [
      { x: 220, y: 360 },
      { x: 360, y: 360 },
      { x: 360, y: 620 },
      { x: 220, y: 360 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    fireEvent.click(
      screen.getByRole("button", { name: "拒绝本次圈选" })
    );
    expect(onDismiss).toHaveBeenCalledOnce();
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("mirrors swipe decisions with keyboard arrow controls", () => {
    const { onConfirm, onDismiss, overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 160, y: 80 },
      { x: 160, y: 260 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    const firstLift = screen.getByRole("group", {
      name: "已圈选的穿搭主体"
    });
    firstLift.focus();
    fireEvent.keyDown(firstLift, { key: "ArrowRight" });
    expect(onConfirm).toHaveBeenCalledOnce();

    drawLoop(overlay, 2, [
      { x: 220, y: 360 },
      { x: 360, y: 360 },
      { x: 360, y: 620 },
      { x: 220, y: 360 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    const secondLift = screen.getByRole("group", {
      name: "已圈选的穿搭主体"
    });
    secondLift.focus();
    fireEvent.keyDown(secondLift, { key: "ArrowLeft" });
    expect(onDismiss).toHaveBeenCalledOnce();
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("drops a cancelled in-progress loop while preserving earlier selections", () => {
    const { overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 160, y: 80 },
      { x: 160, y: 260 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(600));

    firePointer(overlay, "pointerdown", {
      pointerId: 2,
      clientX: 220,
      clientY: 360
    });
    firePointer(overlay, "pointermove", {
      pointerId: 2,
      clientX: 360,
      clientY: 360
    });
    firePointer(overlay, "pointercancel", {
      pointerId: 2,
      clientX: 360,
      clientY: 360
    });

    expect(
      screen.queryByRole("img", { name: "正在圈选的炫彩轮廓" })
    ).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(699));
    expect(
      screen.queryByRole("group", { name: "已圈选的穿搭主体" })
    ).not.toBeInTheDocument();

    act(() => vi.advanceTimersByTime(1));
    expect(
      screen.getByRole("group", { name: "已圈选的穿搭主体" })
    ).toHaveAttribute("data-selection-count", "1");
  });

  it("never decides from a cancelled lifted-subject drag", () => {
    const { onConfirm, onDismiss, overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 40, y: 80 },
      { x: 160, y: 80 },
      { x: 160, y: 260 },
      { x: 40, y: 80 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    const lifted = screen.getByRole("group", {
      name: "已圈选的穿搭主体"
    });
    firePointer(lifted, "pointerdown", {
      pointerId: 6,
      clientX: 180,
      clientY: 400
    });
    firePointer(lifted, "pointermove", {
      pointerId: 6,
      clientX: 260,
      clientY: 400
    });
    firePointer(lifted, "pointercancel", {
      pointerId: 6,
      clientX: 260,
      clientY: 400
    });
    firePointer(lifted, "pointerup", {
      pointerId: 6,
      clientX: 320,
      clientY: 400
    });

    expect(onConfirm).not.toHaveBeenCalled();
    expect(onDismiss).not.toHaveBeenCalled();
    expect(
      screen.getByRole("group", { name: "已圈选的穿搭主体" })
    ).toBeInTheDocument();
  });

  it("treats an empty tap as resume while no garment loop exists", () => {
    const { onConfirm, onDismiss, onEmptyTap, overlay } = renderOverlay();
    firePointer(overlay, "pointerdown", {
      pointerId: 1,
      clientX: 120,
      clientY: 240
    });
    firePointer(overlay, "pointerup", {
      pointerId: 1,
      clientX: 120,
      clientY: 240
    });

    act(() => vi.advanceTimersByTime(700));
    expect(
      screen.queryByRole("group", { name: "已圈选的穿搭主体" })
    ).not.toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onDismiss).not.toHaveBeenCalled();
    expect(onEmptyTap).toHaveBeenCalledOnce();
  });

  it("treats normal finger jitter as a tap instead of trapping the paused guide", () => {
    const { onEmptyTap, overlay } = renderOverlay();
    firePointer(overlay, "pointerdown", {
      pointerId: 1,
      clientX: 120,
      clientY: 240
    });
    firePointer(overlay, "pointermove", {
      pointerId: 1,
      clientX: 130,
      clientY: 246
    });
    firePointer(overlay, "pointermove", {
      pointerId: 1,
      clientX: 137,
      clientY: 251
    });
    firePointer(overlay, "pointerup", {
      pointerId: 1,
      clientX: 135,
      clientY: 249
    });

    expect(onEmptyTap).toHaveBeenCalledOnce();
  });

  it("keeps tiny accidental loops out of the save flow and asks for a larger lasso", () => {
    const { onConfirm, onDismiss, onEmptyTap, overlay } = renderOverlay();
    drawLoop(overlay, 1, [
      { x: 120, y: 240 },
      { x: 140, y: 240 },
      { x: 140, y: 260 },
      { x: 120, y: 240 }
    ]);

    act(() => vi.advanceTimersByTime(700));

    expect(
      screen.getByRole("status", { name: "圈选太小" })
    ).toHaveTextContent("圈大一点");
    expect(
      screen.queryByRole("group", { name: "已圈选的穿搭主体" })
    ).not.toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onDismiss).not.toHaveBeenCalled();
    expect(onEmptyTap).not.toHaveBeenCalled();
  });

  it("shows a non-blocking drawing guide and can replay it", () => {
    const { view } = renderOverlay({ gestureGuideToken: 1 });

    expect(
      screen.getByRole("status", { name: "沿着衣服边缘画一圈" })
    ).toBeInTheDocument();

    view.rerender(
      <FeedSelectionOverlay
        frame={frame}
        frameImageUrl="blob:current-feed-frame"
        gestureGuideToken={2}
        videoSize={{ width: 1080, height: 2160 }}
        onConfirm={vi.fn()}
        onDismiss={vi.fn()}
        onEmptyTap={vi.fn()}
      />
    );

    expect(
      screen.getByRole("status", { name: "沿着衣服边缘画一圈" })
    ).toHaveAttribute("data-guide-token", "2");
  });

  it("teaches the first Feed users what to do after the subject lifts", () => {
    const { overlay } = renderOverlay({ gestureGuideToken: 1 });

    drawLoop(overlay, 31, [
      { x: 120, y: 220 },
      { x: 280, y: 220 },
      { x: 280, y: 560 },
      { x: 120, y: 560 },
      { x: 120, y: 220 }
    ]);
    act(() => vi.advanceTimersByTime(700));

    expect(
      screen.getByRole("status", { name: "左划取消，右划加入" })
    ).toHaveTextContent("左划取消");
    expect(
      screen.getByRole("status", { name: "左划取消，右划加入" })
    ).toHaveTextContent("右划加入");
  });
});
