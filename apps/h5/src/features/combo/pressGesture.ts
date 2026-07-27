/**
 * 区分「点一下」「长按拖」「在滑列表」三件事。
 *
 * 这三种手势在触摸屏上开头完全一样——都是一根手指按下去。判错的后果很具体：
 * 想开详情却把卡片拖起来了，或者想滑列表结果整页卡住。所以规则要写死，而不是
 * 靠感觉调：
 *
 *   按下后手指移动超过 MOVE_TOLERANCE  → 判定为滑列表，这次手势作废
 *   按住超过 LONG_PRESS_MS 且几乎没动 → 进入拖拽
 *   在长按成立前抬手且几乎没动        → 判定为点击
 *
 * 只有"几乎没动"的长按才会变成拖拽，所以列表滚动永远优先——用户滑不动页面是
 * 比拖不动卡片严重得多的问题。
 *
 * 这里是纯状态机，不碰 DOM，方便把三条分支分别测穿。
 */

export const LONG_PRESS_MS = 450;
export const MOVE_TOLERANCE = 10;

export type PressPhase = "idle" | "pressing" | "dragging" | "abandoned";

export type PressState = {
  phase: PressPhase;
  startX: number;
  startY: number;
  startedAt: number;
  /** 当前指针位置，拖拽时用来画跟随的影子。 */
  x: number;
  y: number;
};

export type PressOutcome = "none" | "click" | "drop";

export function idlePress(): PressState {
  return { phase: "idle", startX: 0, startY: 0, startedAt: 0, x: 0, y: 0 };
}

export function pressDown(x: number, y: number, now: number): PressState {
  return { phase: "pressing", startX: x, startY: y, startedAt: now, x, y };
}

function travelled(state: PressState, x: number, y: number): number {
  return Math.hypot(x - state.startX, y - state.startY);
}

export function pressMove(
  state: PressState,
  x: number,
  y: number,
  now: number
): PressState {
  if (state.phase === "dragging") return { ...state, x, y };
  if (state.phase !== "pressing") return state;

  const moved = travelled(state, x, y);
  if (moved <= MOVE_TOLERANCE) return { ...state, x, y };

  // 动得太多。长按已经成立就继续拖，否则就是在滑列表。
  return now - state.startedAt >= LONG_PRESS_MS
    ? { ...state, phase: "dragging", x, y }
    : { ...state, phase: "abandoned", x, y };
}

/** 长按计时器到点时调用。手指此刻仍需停在原处。 */
export function pressHeld(state: PressState, now: number): PressState {
  if (state.phase !== "pressing") return state;
  if (now - state.startedAt < LONG_PRESS_MS) return state;
  if (travelled(state, state.x, state.y) > MOVE_TOLERANCE) return state;
  return { ...state, phase: "dragging" };
}

export function pressUp(
  state: PressState,
  now: number
): { state: PressState; outcome: PressOutcome } {
  if (state.phase === "dragging") {
    return { state: idlePress(), outcome: "drop" };
  }
  if (state.phase === "pressing") {
    const quick = now - state.startedAt < LONG_PRESS_MS;
    const still = travelled(state, state.x, state.y) <= MOVE_TOLERANCE;
    return { state: idlePress(), outcome: quick && still ? "click" : "none" };
  }
  return { state: idlePress(), outcome: "none" };
}

export function pressCancel(): PressState {
  return idlePress();
}
