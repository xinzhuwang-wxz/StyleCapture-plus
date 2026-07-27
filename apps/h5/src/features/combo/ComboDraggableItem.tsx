import { useEffect } from "react";

import type { Item } from "../../api/client";
import { garmentLabel } from "../wardrobe/localization";
import { WardrobeItemCard } from "../wardrobe/ItemCard";
import { useLongPressDrag } from "./useLongPressDrag";

type ComboDraggableItemProps = {
  item: Item;
  inBasket: boolean;
  onOpen: () => void;
  onRetry: () => void;
  onRetryPixel: () => void;
  onToggleBasket: (label: string) => void;
  onDragActive: (active: boolean) => void;
};

/**
 * 给衣橱卡片加上「长按拖进组合衣柜」。
 *
 * 拖拽在这里是增强：同一张卡片上的「加入组合」按钮做的是同一件事，键盘和读屏
 * 用户走那条路。所以即使指针手势在某台设备上完全失灵，功能依然完整。
 */
export function ComboDraggableItem({
  item,
  inBasket,
  onOpen,
  onRetry,
  onRetryPixel,
  onToggleBasket,
  onDragActive
}: ComboDraggableItemProps) {
  const label = garmentLabel(
    item.attributes.subcategory?.value ?? item.attributes.category?.value
  );

  const { handlers, dragging, point } = useLongPressDrag({
    onDragStart: () => onDragActive(true),
    onDrop: () => {
      onDragActive(false);
      if (!inBasket) onToggleBasket(label);
    }
  });

  // 拖拽被系统打断（来电、切后台）时也要把落点高亮收回去。
  useEffect(() => {
    if (!dragging) onDragActive(false);
  }, [dragging, onDragActive]);

  return (
    <>
      <WardrobeItemCard
        item={item}
        onOpen={onOpen}
        onRetry={onRetry}
        onRetryPixel={onRetryPixel}
        combo={{
          inBasket,
          onToggle: () => onToggleBasket(label),
          dragHandlers: {
            ...handlers,
            style: dragging ? { touchAction: "none" } : undefined
          }
        }}
      />
      {dragging && point ? (
        <img
          className="combo-ghost"
          src={item.display_image_url ?? ""}
          alt=""
          aria-hidden="true"
          style={{ left: point.x, top: point.y }}
        />
      ) : null}
    </>
  );
}
