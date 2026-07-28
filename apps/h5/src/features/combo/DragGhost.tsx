import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

type DragGhostProps = {
  imageUrl: string | null;
  startX: number;
  startY: number;
};

/**
 * 跟着手指走的那张卡。
 *
 * 两个坑都出在「它渲染在哪」和「谁来更新它」：
 *
 * - 卡片是 motion.article，带 transform。有 transform 的祖先会成为
 *   position:fixed 的包含块，于是拖影被困在卡片那一小块里，看起来像
 *   「只能在很小范围内拖动」。挂到 document.body 上才真的能满屏走。
 * - 每次 pointermove 都 setState，会把整张卡连同图片一起重渲染，所以拖起来
 *   一卡一卡。这里改成自己听 window 的事件、直接写 style.transform，
 *   React 全程不参与移动。
 */
export function DragGhost({ imageUrl, startX, startY }: DragGhostProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const place = (x: number, y: number) => {
      node.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, -50%) rotate(-4deg)`;
    };
    place(startX, startY);
    const onMove = (event: PointerEvent) => place(event.clientX, event.clientY);
    // 捕获阶段监听，免得中途有人 stopPropagation 把移动吃掉。
    window.addEventListener("pointermove", onMove, true);
    return () => window.removeEventListener("pointermove", onMove, true);
  }, [startX, startY]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="combo-ghost" ref={ref} aria-hidden="true">
      {imageUrl ? <img src={imageUrl} alt="" /> : null}
      <span className="combo-ghost__hint">松手放进衣柜 · Esc 取消</span>
    </div>,
    document.body
  );
}
