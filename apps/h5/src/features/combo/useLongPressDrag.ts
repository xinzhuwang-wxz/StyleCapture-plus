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
  onClickCapture: (event: React.MouseEvent) => void;
};

type UseLongPressDragOptions = {
  onDragStart?: () => void;
  /** 手指落在衣柜上松开时调用。落在别处松开算取消，不会调。 */
  onDrop: () => void;
  /** 判断松手位置算不算落进衣柜。 */
  isOverTarget?: (x: number, y: number) => boolean;
  disabled?: boolean;
};

/**
 * 长按拖拽。
 *
 * 所有指针事件都挂在 window 上，而不是卡片上。挂在卡片上时，只要手指离开
 * 卡片再松开，pointerup 就永远不会到达，`dragging` 卡在 true，拖影会一直
 * 跟着鼠标不消失——这个 bug 真机上遇到过。挂 window 之后，无论在哪松手都
 * 一定收尾。
 *
 * 另外补了三条退路：Esc 取消、窗口失焦取消、页面切到后台取消。拖拽没有
 * 「反悔」入口是很难受的。
 */
export function useLongPressDrag({
  onDragStart,
  onDrop,
  isOverTarget,
  disabled
}: UseLongPressDragOptions): {
  handlers: DragHandlers;
  dragging: boolean;
  origin: { x: number; y: number } | null;
} {
  const stateRef = useRef<PressState>(idlePress());
  const timerRef = useRef(0);
  // 拖完手指抬起时浏览器仍会补一个 click。不吞掉它，放手就会顺带打开详情。
  const swallowClick = useRef(false);
  const [dragging, setDragging] = useState(false);
  const [origin, setOrigin] = useState<{ x: number; y: number } | null>(null);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = 0;
    }
  }, []);

  const finish = useCallback(() => {
    stopTimer();
    stateRef.current = pressCancel();
    setDragging(false);
    setOrigin(null);
  }, [stopTimer]);

  const enterDrag = useCallback(() => {
    setDragging(true);
    setOrigin({ x: stateRef.current.x, y: stateRef.current.y });
    onDragStart?.();
    // 轻微震动是「你已经拿起来了」最直接的反馈；没有这个能力就算了。
    if (typeof navigator !== "undefined" && "vibrate" in navigator) {
      navigator.vibrate?.(12);
    }
  }, [onDragStart]);

  // 一次按压的全过程都由 window 上的这组监听收尾。
  useEffect(() => {
    if (stateRef.current.phase === "idle" && !dragging) return;

    const onMove = (event: PointerEvent) => {
      if (stateRef.current.phase === "idle") return;
      const before = stateRef.current.phase;
      const next = pressMove(
        stateRef.current,
        event.clientX,
        event.clientY,
        Date.now()
      );
      stateRef.current = next;
      if (next.phase === "dragging" && before !== "dragging") enterDrag();
      if (next.phase === "abandoned") stopTimer();
      // 拖起来之后别让页面跟着滚。
      if (next.phase === "dragging" && event.cancelable) event.preventDefault();
    };

    const onUp = (event: PointerEvent) => {
      stopTimer();
      const wasDragging = stateRef.current.phase === "dragging";
      const { state, outcome } = pressUp(stateRef.current, Date.now());
      stateRef.current = state;
      setDragging(false);
      setOrigin(null);
      if (outcome !== "drop" || !wasDragging) return;
      swallowClick.current = true;
      /*
       * 松手时浏览器会给「手指下面那个东西」补一个 click——那通常不是被拖的
       * 卡片，而是落点处的另一张卡，于是一放手就跳进了别人的详情页。
       * 所以这一下要全局吞掉，只吞一次。
       */
      const swallow = (click: MouseEvent) => {
        click.preventDefault();
        click.stopPropagation();
      };
      window.addEventListener("click", swallow, { capture: true, once: true });
      // 万一浏览器这次没补 click，别把监听留到下一次真实点击上。
      window.setTimeout(
        () => window.removeEventListener("click", swallow, true),
        300
      );
      // 没落在衣柜上就是「不想放了」，安静收回，不硬塞。
      if (isOverTarget && !isOverTarget(event.clientX, event.clientY)) return;
      onDrop();
    };

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") finish();
    };

    window.addEventListener("pointermove", onMove, { passive: false });
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", finish);
    window.addEventListener("keydown", onKey);
    window.addEventListener("blur", finish);
    document.addEventListener("visibilitychange", finish);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", finish);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("blur", finish);
      document.removeEventListener("visibilitychange", finish);
    };
  }, [dragging, enterDrag, finish, isOverTarget, onDrop, stopTimer]);

  useEffect(() => stopTimer, [stopTimer]);

  const handlers: DragHandlers = {
    onPointerDown: (event) => {
      if (disabled) return;
      // 卡片里还有「加入组合」「重新识别」这些按钮，它们有自己的职责，
      // 手势不该把它们的点击也接管过去。
      if (
        (event.target as Element | null)?.closest?.(
          "button.combo-add, button.retry-link"
        )
      ) {
        return;
      }
      stateRef.current = pressDown(event.clientX, event.clientY, Date.now());
      // 触发一次重渲染，好让上面那组 window 监听装上去。
      setOrigin({ x: event.clientX, y: event.clientY });
      stopTimer();
      timerRef.current = window.setTimeout(() => {
        const next = pressHeld(stateRef.current, Date.now());
        stateRef.current = next;
        if (next.phase === "dragging") enterDrag();
      }, LONG_PRESS_MS);
    },
    onClickCapture: (event) => {
      if (!swallowClick.current) return;
      swallowClick.current = false;
      event.preventDefault();
      event.stopPropagation();
    }
  };

  return { handlers, dragging, origin };
}
