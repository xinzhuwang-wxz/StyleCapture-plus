import { useCallback, useEffect, useRef, useState } from "react";

import {
  LONG_PRESS_MS,
  idlePress,
  pressCancel,
  pressDown,
  pressHeld,
  pressMove,
  pressUp,
  type PressState
} from "./pressGesture";

type DragHandlers = {
  onPointerDown: (event: React.PointerEvent) => void;
  onPointerMove: (event: React.PointerEvent) => void;
  onPointerUp: (event: React.PointerEvent) => void;
  onPointerCancel: () => void;
  onClickCapture: (event: React.MouseEvent) => void;
};

type UseLongPressDragOptions = {
  onDragStart?: () => void;
  onDrop: () => void;
  disabled?: boolean;
};

/**
 * 把指针事件接到手势状态机上。
 *
 * 两点值得说明：
 * - 只有真正进入拖拽后才 setPointerCapture。捕获得太早会把列表滚动一起吞掉。
 * - touch-action 同理，只在拖拽期间关掉：滑不动页面比拖不动卡片严重得多。
 */
export function useLongPressDrag({
  onDragStart,
  onDrop,
  disabled
}: UseLongPressDragOptions): {
  handlers: DragHandlers;
  dragging: boolean;
  point: { x: number; y: number } | null;
} {
  const stateRef = useRef<PressState>(idlePress());
  const timerRef = useRef(0);
  // 拖完手指抬起时浏览器仍会补一个 click。不吞掉它，放手就会顺带打开详情。
  const swallowClick = useRef(false);
  const [dragging, setDragging] = useState(false);
  const [point, setPoint] = useState<{ x: number; y: number } | null>(null);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = 0;
    }
  }, []);

  useEffect(() => stopTimer, [stopTimer]);

  const enterDrag = useCallback(() => {
    setDragging(true);
    setPoint({ x: stateRef.current.x, y: stateRef.current.y });
    onDragStart?.();
    // 轻微震动是"你已经拿起来了"最直接的反馈；没有这个能力就算了。
    if (typeof navigator !== "undefined" && "vibrate" in navigator) {
      navigator.vibrate?.(12);
    }
  }, [onDragStart]);

  const handlers: DragHandlers = {
    onPointerDown: (event) => {
      if (disabled) return;
      // 卡片里还有「加入组合」「重新识别」这些按钮，它们有自己的职责，
      // 手势不该把它们的点击也接管过去。
      if ((event.target as Element | null)?.closest?.("button.combo-add, button.retry-link")) {
        return;
      }
      stateRef.current = pressDown(event.clientX, event.clientY, Date.now());
      stopTimer();
      timerRef.current = window.setTimeout(() => {
        const next = pressHeld(stateRef.current, Date.now());
        stateRef.current = next;
        if (next.phase === "dragging") enterDrag();
      }, LONG_PRESS_MS);
    },
    onPointerMove: (event) => {
      if (stateRef.current.phase === "idle") return;
      const before = stateRef.current.phase;
      const next = pressMove(
        stateRef.current,
        event.clientX,
        event.clientY,
        Date.now()
      );
      stateRef.current = next;
      if (next.phase === "dragging") {
        if (before !== "dragging") {
          enterDrag();
          event.currentTarget.setPointerCapture?.(event.pointerId);
        } else {
          setPoint({ x: next.x, y: next.y });
        }
      } else if (next.phase === "abandoned") {
        stopTimer();
      }
    },
    onPointerUp: () => {
      stopTimer();
      const { state, outcome } = pressUp(stateRef.current, Date.now());
      stateRef.current = state;
      setDragging(false);
      setPoint(null);
      if (outcome === "drop") {
        swallowClick.current = true;
        onDrop();
      }
    },
    onPointerCancel: () => {
      stopTimer();
      stateRef.current = pressCancel();
      setDragging(false);
      setPoint(null);
    },
    onClickCapture: (event) => {
      if (!swallowClick.current) return;
      swallowClick.current = false;
      event.preventDefault();
      event.stopPropagation();
    }
  };

  return { handlers, dragging, point };
}
