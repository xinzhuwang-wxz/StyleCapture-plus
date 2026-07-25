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
  videoSize: ViewportSize;
  onConfirm: (decision: FeedSelectionDecision) => void;
  onDismiss: () => void;
}

export interface FeedSelectionDecision {
  frame: FeedFrameIdentity;
  selections: readonly ClosedFeedSelection[];
}

const SWIPE_DECISION_THRESHOLD_PX = 88;

export function FeedSelectionOverlay(props: FeedSelectionOverlayProps) {
  const [session, setSession] = useState(createSelectionSession);
  const [activePoints, setActivePoints] = useState<ViewportPoint[]>([]);
  const [contentBox, setContentBox] = useState<VideoContentBox | null>(null);
  const [dragOffsetX, setDragOffsetX] = useState(0);
  const pointsRef = useRef<ViewportPoint[]>([]);
  const selectionNumberRef = useRef(0);
  const dragRef = useRef<{ pointerId: number; startX: number } | null>(null);
  const trailGradientId = useId().replaceAll(":", "");
  const clipId = useId().replaceAll(":", "");
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (session.phase !== "collecting" || session.settleAtMs === null) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setSession((current) => settleSelectionSession(current, Date.now()));
    }, Math.max(0, session.settleAtMs - Date.now()));

    return () => window.clearTimeout(timeout);
  }, [session.phase, session.settleAtMs]);

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
    const path = closeNormalizedLasso(
      pointsRef.current,
      measuredContentBox
    );
    pointsRef.current = [];
    setActivePoints([]);
    if (!path) {
      setSession((current) => cancelSelectionLoop(current, Date.now()));
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
    setSession(createSelectionSession());
  };

  const confirmSelection = () => {
    if (!session.frame || session.selections.length === 0) {
      return;
    }
    props.onConfirm({
      frame: session.frame,
      selections: session.selections
    });
    resetSelection();
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
      aria-label="圈选穿搭"
      className="feed-selection-overlay"
      role="application"
      onPointerDown={onPointerDown}
      onPointerCancel={onPointerCancel}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
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
          >
            <button
              aria-label="拒绝本次圈选"
              className="feed-selection-action feed-selection-action--dismiss"
              type="button"
              onClick={dismissSelection}
            >
              ←
            </button>
            <button
              aria-label="保存圈选到数字衣橱"
              className="feed-selection-action feed-selection-action--confirm"
              type="button"
              onClick={confirmSelection}
            >
              收藏
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
