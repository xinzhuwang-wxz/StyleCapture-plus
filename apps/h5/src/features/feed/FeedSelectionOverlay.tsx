import { motion, useReducedMotion } from "motion/react";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent
} from "react";

import "./feed.css";

import { closeNormalizedLasso } from "./lasso";
import {
  beginSelectionLoop,
  cancelSelectionLoop,
  completeSelectionLoop,
  createSelectionSession,
  settleSelectionSession,
  type ClosedFeedSelection,
  type FeedFrameIdentity
} from "./selectionSession";
import {
  contentBoxForContainedVideo,
  denormalizeVideoPoint,
  type VideoContentBox,
  type ViewportPoint,
  type ViewportSize
} from "./viewport";

export interface FeedSelectionOverlayProps {
  frame: FeedFrameIdentity;
  frameImageUrl: string;
  gestureGuideToken?: number;
  videoSize: ViewportSize;
  onConfirm: (decision: FeedSelectionDecision) => void;
  onDismiss: () => void;
  onEmptyTap: () => void;
}

export interface FeedSelectionDecision {
  frame: FeedFrameIdentity;
  intent: "item_selections" | "whole_outfit";
  selections: readonly ClosedFeedSelection[];
}

const SWIPE_DECISION_THRESHOLD_PX = 88;
const EMPTY_TAP_MAX_DISTANCE_PX = 12;
const WHOLE_FRAME_SELECTION: ClosedFeedSelection = {
  id: "whole-outfit-full-frame",
  path: [
    { x: 0, y: 0 },
    { x: 1, y: 0 },
    { x: 1, y: 1 },
    { x: 0, y: 1 }
  ]
};

function isEmptyTap(points: readonly ViewportPoint[]) {
  const first = points[0];
  if (!first || points.length > 2) {
    return false;
  }
  return points.every(
    (point) =>
      Math.hypot(point.x - first.x, point.y - first.y) <=
      EMPTY_TAP_MAX_DISTANCE_PX
  );
}

export function FeedSelectionOverlay(props: FeedSelectionOverlayProps) {
  const [session, setSession] = useState(createSelectionSession);
  const [activePoints, setActivePoints] = useState<ViewportPoint[]>([]);
  const [contentBox, setContentBox] = useState<VideoContentBox | null>(null);
  const [dragOffsetX, setDragOffsetX] = useState(0);
  const [guideVisible, setGuideVisible] = useState(
    Boolean(props.gestureGuideToken)
  );
  const [decisionGuideVisible, setDecisionGuideVisible] = useState(false);
  const [intent, setIntent] =
    useState<FeedSelectionDecision["intent"]>("item_selections");
  const pointsRef = useRef<ViewportPoint[]>([]);
  const selectionNumberRef = useRef(0);
  const dragRef = useRef<{ pointerId: number; startX: number } | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const trailGradientId = useId().replaceAll(":", "");
  const clipId = useId().replaceAll(":", "");
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (!props.gestureGuideToken) {
      setGuideVisible(false);
      return;
    }
    setGuideVisible(true);
    const timeout = window.setTimeout(
      () => setGuideVisible(false),
      reduceMotion ? 2_400 : 1_900
    );
    return () => window.clearTimeout(timeout);
  }, [props.gestureGuideToken, reduceMotion]);

  useEffect(() => {
    if (session.phase !== "collecting" || session.settleAtMs === null) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setSession((current) => settleSelectionSession(current, Date.now()));
    }, Math.max(0, session.settleAtMs - Date.now()));

    return () => window.clearTimeout(timeout);
  }, [session.phase, session.settleAtMs]);

  useEffect(() => {
    if (session.phase !== "settled" || !props.gestureGuideToken) {
      setDecisionGuideVisible(false);
      return;
    }
    setDecisionGuideVisible(true);
    const timeout = window.setTimeout(
      () => setDecisionGuideVisible(false),
      reduceMotion ? 2_800 : 2_200
    );
    return () => window.clearTimeout(timeout);
  }, [props.gestureGuideToken, reduceMotion, session.phase]);

  const contentBoxFor = (element: HTMLElement) => {
    const rect = element.getBoundingClientRect();
    return contentBoxForContainedVideo(
      { width: rect.width, height: rect.height },
      props.videoSize
    );
  };

  const pointFor = (
    event: ReactPointerEvent<HTMLDivElement>
  ): ViewportPoint => {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    };
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (session.phase === "settled") {
      return;
    }
    const measuredContentBox = contentBoxFor(event.currentTarget);
    if (!measuredContentBox) {
      return;
    }
    const start = pointFor(event);
    setGuideVisible(false);
    pointsRef.current = [start];
    setActivePoints([start]);
    setContentBox(measuredContentBox);
    setSession((current) => beginSelectionLoop(current, props.frame));
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (pointsRef.current.length === 0) {
      return;
    }
    pointsRef.current = [...pointsRef.current, pointFor(event)];
    setActivePoints(pointsRef.current);
  };

  const onPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (pointsRef.current.length === 0) {
      return;
    }
    const measuredContentBox = contentBoxFor(event.currentTarget);
    if (!measuredContentBox) {
      pointsRef.current = [];
      setActivePoints([]);
      setSession((current) => cancelSelectionLoop(current, Date.now()));
      return;
    }
    const rawPoints = pointsRef.current;
    const path = closeNormalizedLasso(rawPoints, measuredContentBox);
    pointsRef.current = [];
    setActivePoints([]);
    if (!path) {
      setSession((current) => cancelSelectionLoop(current, Date.now()));
      if (session.selections.length === 0 && isEmptyTap(rawPoints)) {
        props.onEmptyTap();
      }
      return;
    }
    selectionNumberRef.current += 1;
    setSession((current) =>
      completeSelectionLoop(
        current,
        {
          id: `selection-${selectionNumberRef.current}`,
          path
        },
        Date.now()
      )
    );
  };

  const onPointerCancel = () => {
    if (pointsRef.current.length === 0) {
      return;
    }
    pointsRef.current = [];
    setActivePoints([]);
    setSession((current) => cancelSelectionLoop(current, Date.now()));
  };

  const elementPointsFor = (path: readonly ViewportPoint[]) =>
    contentBox
      ? path.map((point) => denormalizeVideoPoint(point, contentBox))
      : [];

  const normalizedPathData = session.selections
    .map((selection) =>
      selection.path
        .map(
          (point, index) =>
            `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`
        )
        .join(" ")
    )
    .map((path) => `${path} Z`)
    .join(" ");

  const resetSelection = () => {
    pointsRef.current = [];
    setActivePoints([]);
    setDragOffsetX(0);
    setIntent("item_selections");
    setSession(createSelectionSession());
  };

  const confirmSelection = () => {
    if (!session.frame || session.selections.length === 0) {
      return;
    }
    props.onConfirm({
      frame: session.frame,
      intent,
      selections: session.selections
    });
    resetSelection();
  };

  const confirmWholeFrame = () => {
    if (!overlayRef.current) return;
    const measuredContentBox = contentBoxFor(overlayRef.current);
    if (!measuredContentBox) return;
    setGuideVisible(false);
    setContentBox(measuredContentBox);
    setIntent("whole_outfit");
    setSession({
      phase: "settled",
      frame: props.frame,
      selections: [WHOLE_FRAME_SELECTION],
      settleAtMs: null
    });
  };

  const continueSelecting = () => {
    setDragOffsetX(0);
    setIntent("item_selections");
    setSession((current) => ({
      ...current,
      phase: "collecting",
      settleAtMs: null
    }));
  };

  const dismissSelection = () => {
    props.onDismiss();
    resetSelection();
  };

  const onLiftedPointerDown = (
    event: ReactPointerEvent<HTMLDivElement>
  ) => {
    event.stopPropagation();
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const onLiftedPointerMove = (
    event: ReactPointerEvent<HTMLDivElement>
  ) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }
    event.stopPropagation();
    setDragOffsetX(event.clientX - drag.startX);
  };

  const onLiftedPointerUp = (
    event: ReactPointerEvent<HTMLDivElement>
  ) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) {
      return;
    }
    event.stopPropagation();
    dragRef.current = null;
    const distance = event.clientX - drag.startX;
    if (distance >= SWIPE_DECISION_THRESHOLD_PX) {
      confirmSelection();
    } else if (distance <= -SWIPE_DECISION_THRESHOLD_PX) {
      dismissSelection();
    } else {
      setDragOffsetX(0);
    }
  };

  const onLiftedPointerCancel = (
    event: ReactPointerEvent<HTMLDivElement>
  ) => {
    event.stopPropagation();
    dragRef.current = null;
    setDragOffsetX(0);
  };

  const onLiftedKeyDown = (
    event: ReactKeyboardEvent<HTMLDivElement>
  ) => {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      confirmSelection();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      dismissSelection();
    }
  };

  return (
    <div
      ref={overlayRef}
      aria-label="圈选穿搭"
      className="feed-selection-overlay"
      role="application"
      onPointerDown={onPointerDown}
      onPointerCancel={onPointerCancel}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      {session.selections.length === 0 ? (
        <button
          aria-label="一键保存整套穿搭"
          className="feed-whole-outfit-shortcut"
          type="button"
          onPointerDown={(event) => event.stopPropagation()}
          onClick={confirmWholeFrame}
        >
          一键存整套
        </button>
      ) : null}

      {guideVisible && session.selections.length === 0 ? (
        <div
          aria-label="沿着衣服边缘画一圈"
          className="feed-selection-guide"
          data-guide-token={props.gestureGuideToken}
          role="status"
        >
          <svg aria-hidden="true" viewBox="0 0 180 230">
            <path d="M 88 28 C 142 28 157 80 146 126 C 137 177 95 202 53 174 C 17 150 22 91 44 54 C 55 35 69 29 88 28 Z" />
          </svg>
          <motion.span
            aria-hidden="true"
            animate={
              reduceMotion
                ? undefined
                : {
                    x: [0, 48, 58, 20, -30, -42, 0],
                    y: [-76, -54, 4, 58, 42, -16, -76],
                    rotate: [0, 12, 20, 8, -12, -18, 0]
                  }
            }
            className="feed-selection-guide__hand"
            transition={{
              duration: 1.45,
              ease: "easeInOut",
              times: [0, 0.18, 0.34, 0.54, 0.7, 0.86, 1]
            }}
          >
            ☝︎
          </motion.span>
          <strong>沿衣服边缘画一圈</strong>
          <small>轻点画面可继续播放</small>
        </div>
      ) : null}

      {activePoints.length > 1 ? (
        <svg
          aria-label="正在圈选的炫彩轮廓"
          className="feed-lasso-layer"
          role="img"
        >
          <defs>
            <linearGradient id={trailGradientId} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#66f5ff" />
              <stop offset="46%" stopColor="#a773ff" />
              <stop offset="100%" stopColor="#ff5ec4" />
            </linearGradient>
          </defs>
          <polyline
            className="feed-lasso-trail"
            points={activePoints.map((point) => `${point.x},${point.y}`).join(" ")}
            stroke={`url(#${trailGradientId})`}
          />
        </svg>
      ) : null}

      {session.phase === "collecting" && contentBox ? (
        <svg
          aria-label="已圈选的炫彩轮廓"
          className="feed-lasso-layer"
          role="img"
        >
          {session.selections.map((selection) => (
            <polygon
              className="feed-lasso-trail feed-lasso-trail--closed"
              key={selection.id}
              points={elementPointsFor(selection.path)
                .map((point) => `${point.x},${point.y}`)
                .join(" ")}
            />
          ))}
        </svg>
      ) : null}

      {session.phase === "settled" && contentBox ? (
        <>
          {decisionGuideVisible ? (
            <div
              aria-label="左划取消，右划加入"
              className="feed-swipe-guide"
              role="status"
            >
              <span>← 左划取消</span>
              <motion.b
                aria-hidden="true"
                animate={reduceMotion ? undefined : { x: [0, -28, 0, 28, 0] }}
                transition={{ duration: 1.35, ease: "easeInOut" }}
              >
                ☝︎
              </motion.b>
              <span>右划加入 →</span>
            </div>
          ) : null}
          <motion.div
            aria-label="已圈选的穿搭主体"
            className="feed-lifted-selection"
            data-selection-count={session.selections.length}
            animate={{
              x: dragOffsetX,
              y: reduceMotion ? 0 : -8,
              scale: reduceMotion ? 1 : 1.025
            }}
            onKeyDown={onLiftedKeyDown}
            onPointerCancel={onLiftedPointerCancel}
            onPointerDown={onLiftedPointerDown}
            onPointerMove={onLiftedPointerMove}
            onPointerUp={onLiftedPointerUp}
            role="group"
            style={{
              left: contentBox.x,
              top: contentBox.y,
              width: contentBox.width,
              height: contentBox.height
            }}
            tabIndex={0}
            transition={
              reduceMotion
                ? { duration: 0 }
                : { type: "spring", stiffness: 360, damping: 30 }
            }
          >
            <svg viewBox="0 0 1 1" preserveAspectRatio="none">
              <defs>
                <clipPath id={clipId} clipPathUnits="objectBoundingBox">
                  <path d={normalizedPathData} />
                </clipPath>
              </defs>
              <image
                aria-label="当前帧中已圈选的穿搭"
                clipPath={`url(#${clipId})`}
                height="1"
                href={props.frameImageUrl}
                preserveAspectRatio="none"
                role="img"
                width="1"
              />
            </svg>
          </motion.div>
          <div
            aria-label="圈选决策"
            className="feed-selection-actions"
            role="group"
            onPointerDown={(event) => event.stopPropagation()}
          >
            <div className="feed-intent-toggle" aria-label="保存方式">
              <button
                aria-pressed={intent === "item_selections"}
                className={intent === "item_selections" ? "is-selected" : ""}
                type="button"
                onClick={() => setIntent("item_selections")}
              >
                {session.selections.length > 1 ? "存这些单品" : "存单品"}
              </button>
              <button
                aria-pressed={intent === "whole_outfit"}
                className={intent === "whole_outfit" ? "is-selected" : ""}
                disabled={session.selections.length !== 1}
                type="button"
                onClick={() => setIntent("whole_outfit")}
              >
                存整套
              </button>
            </div>
            <button
              className="feed-selection-continue"
              type="button"
              onClick={continueSelecting}
            >
              继续圈选
            </button>
            <button
              aria-label="拒绝本次圈选"
              className="feed-selection-action feed-selection-action--dismiss"
              type="button"
              onClick={dismissSelection}
            >
              ←
            </button>
            <button
              aria-label={
                intent === "whole_outfit"
                  ? "保存整套到数字衣橱"
                  : "保存圈选到数字衣橱"
              }
              className="feed-selection-action feed-selection-action--confirm"
              type="button"
              onClick={confirmSelection}
            >
              {intent === "whole_outfit" ? "存整套" : "收藏"}
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
