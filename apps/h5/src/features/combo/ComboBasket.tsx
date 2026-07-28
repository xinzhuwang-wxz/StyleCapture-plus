import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import type { BasketEntry } from "./basketRules";
import "./combo.css";

type ComboBasketProps = {
  basket: readonly BasketEntry[];
  /** 有人正在拖东西过来，把柜门打开等着接。 */
  receiving?: boolean;
  /** 点柜子进二级页看具体单品。 */
  onOpen: () => void;
};

/**
 * 「我的组合衣柜」——屏幕角上的一个柜子，也是拖拽的落点。
 *
 * 从前它是一条通栏。通栏用的是 position:fixed 加 100% 宽，而演示外壳里
 * 屏幕只有 390px，于是左右都顶出了手机边框。现在挂进 .pixel-screen 里
 * 定位，宽度由内容决定，怎么也溢不出去。
 *
 * 柜门会在东西放进来时开一下再关上——不然「放进去了没有」只能靠角标数字
 * 猜。放进来的动作本身要看得见。
 */
export function ComboBasket({ basket, receiving, onOpen }: ComboBasketProps) {
  const [justReceived, setJustReceived] = useState(false);

  // 件数变多＝刚放进来一件，开门再关上。
  useEffect(() => {
    if (!basket.length) return;
    setJustReceived(true);
    const timer = window.setTimeout(() => setJustReceived(false), 620);
    return () => window.clearTimeout(timer);
  }, [basket.length]);

  const host =
    typeof document === "undefined"
      ? null
      : document.querySelector(".pixel-screen");

  const cabinet = (
    <div
      className="combo-cabinet"
      data-combo-drop-target="true"
      data-receiving={receiving ? "true" : undefined}
      data-swallowing={justReceived ? "true" : undefined}
    >
      <button
        type="button"
        className="combo-cabinet__body"
        aria-label={`我的组合衣柜，已放入 ${basket.length} 件，点开查看`}
        onClick={onOpen}
      >
        <span className="combo-cabinet__doors" aria-hidden="true">
          <span className="combo-cabinet__door combo-cabinet__door--left" />
          <span className="combo-cabinet__door combo-cabinet__door--right" />
        </span>
        <span className="combo-cabinet__count">{basket.length}</span>
      </button>
      <span className="combo-cabinet__label">组合衣柜</span>
    </div>
  );

  return host ? createPortal(cabinet, host) : cabinet;
}
