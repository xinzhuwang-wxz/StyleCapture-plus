import type { ViewportPoint } from "./viewport";

export const SELECTION_SETTLE_DELAY_MS = 700;

export interface FeedFrameIdentity {
  videoId: string;
  timestampMs: number;
}

export interface ClosedFeedSelection {
  id: string;
  path: readonly ViewportPoint[];
}

export type SelectionPhase = "idle" | "drawing" | "collecting" | "settled";

export interface SelectionSession {
  phase: SelectionPhase;
  frame: FeedFrameIdentity | null;
  selections: readonly ClosedFeedSelection[];
  settleAtMs: number | null;
}

export function createSelectionSession(): SelectionSession {
  return {
    phase: "idle",
    frame: null,
    selections: [],
    settleAtMs: null
  };
}

const isSameFrame = (
  current: FeedFrameIdentity,
  next: FeedFrameIdentity
) =>
  current.videoId === next.videoId &&
  current.timestampMs === next.timestampMs;

export function beginSelectionLoop(
  session: SelectionSession,
  frame: FeedFrameIdentity
): SelectionSession {
  if (session.frame && !isSameFrame(session.frame, frame)) {
    throw new Error("A selection session cannot span multiple video frames");
  }

  return {
    ...session,
    phase: "drawing",
    frame,
    settleAtMs: null
  };
}

export function completeSelectionLoop(
  session: SelectionSession,
  selection: ClosedFeedSelection,
  completedAtMs: number
): SelectionSession {
  if (session.phase !== "drawing") {
    throw new Error("A selection loop must begin before it can complete");
  }

  return {
    ...session,
    phase: "collecting",
    selections: [...session.selections, selection],
    settleAtMs: completedAtMs + SELECTION_SETTLE_DELAY_MS
  };
}

export function settleSelectionSession(
  session: SelectionSession,
  nowMs: number
): SelectionSession {
  if (
    session.phase !== "collecting" ||
    session.settleAtMs === null ||
    nowMs < session.settleAtMs
  ) {
    return session;
  }

  return {
    ...session,
    phase: "settled",
    settleAtMs: null
  };
}

export function cancelSelectionLoop(
  session: SelectionSession,
  cancelledAtMs: number
): SelectionSession {
  if (session.phase !== "drawing") {
    return session;
  }

  return session.selections.length === 0
    ? {
        ...session,
        phase: "idle",
        settleAtMs: null
      }
    : {
        ...session,
        phase: "collecting",
        settleAtMs: cancelledAtMs + SELECTION_SETTLE_DELAY_MS
      };
}
