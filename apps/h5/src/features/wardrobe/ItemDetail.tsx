import { PixelButton } from "../../components/PixelUI";
import type { Item } from "../../api/client";
import { douyinShopUrl } from "./catalog";
import { findDisplayItem } from "./displayItem";
import "./itemDetail.css";

interface ItemDetailProps {
  itemId: string;
  /** 衣橱里的真实 Item 列表，新入库的单品也能点进这一页 */
  items: readonly Item[];
  /** 这件是否已经在自由组合的衣柜里 */
  inCombo: boolean;
  onBack: () => void;
  onAddToCombo: (itemId: string) => void;
  onNotice: (message: string) => void;
}

/**
 * 单品详情页（星露谷图鉴风）。
 *
 * 单品有两个交互：单击进这一页，长按拖进悬浮衣柜。这里是前者。
 */
export function ItemDetail({
  itemId,
  items,
  inCombo,
  onBack,
  onAddToCombo,
  onNotice
}: ItemDetailProps) {
  const item = findDisplayItem(items, itemId);

  if (!item) {
    return (
      <div style={{ textAlign: "center", padding: "4rem 1rem" }}>
        <p className="pixel-subtitle">这件单品走丢了</p>
        <PixelButton variant="primary" onClick={onBack}>
          返回
        </PixelButton>
      </div>
    );
  }

  return (
    <div className="pixel-subpage">
      <div className="item-detail__header">
        <PixelButton variant="ghost" onClick={onBack} ariaLabel="返回">
          ‹
        </PixelButton>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="pixel-label" style={{ margin: 0 }}>
            单品图鉴 · {item.category}
          </p>
          <h1 className="pixel-title item-detail__title">{item.name}</h1>
        </div>
        <span
          className="item-detail__own"
          data-owned={item.owned ? "true" : undefined}
        >
          {item.owned ? "⭐ 已拥有" : "未拥有"}
        </span>
      </div>

      <div className="item-detail__hero">
        <img src={item.imageUrl} alt={item.name} data-pixel="true" />
        <div className="item-detail__price">
          {/* 新入库的单品还没有价格，就不摆一个假的出来 */}
          <span>{item.price > 0 ? `¥${item.price}` : "暂无价格"}</span>
          <small>1:1 像素图鉴</small>
        </div>
      </div>

      {/* 星露谷图鉴式的一句话 */}
      <blockquote className="item-detail__lore">{item.lore}</blockquote>

      <section className="item-detail__block">
        <span aria-hidden="true">🤖</span>
        <div style={{ minWidth: 0 }}>
          <p className="pixel-label" style={{ margin: "0 0 4px" }}>
            AI 风格解读
          </p>
          <p className="item-detail__body">{item.styleReading}</p>
        </div>
      </section>

      <section className="item-detail__block item-detail__block--plain">
        <div style={{ minWidth: 0 }}>
          <p className="pixel-label" style={{ margin: "0 0 4px" }}>
            商品描述
          </p>
          <p className="item-detail__body">{item.description}</p>
        </div>
      </section>

      <div style={{ display: "grid", gap: "10px" }}>
        <button
          type="button"
          className="item-detail__shop"
          onClick={() => {
            window.open(douyinShopUrl(item.name), "_blank", "noreferrer");
            onNotice("正在打开抖音商城 🛍");
          }}
        >
          {item.owned ? "🛍 看同款商品链接" : "🛍 去抖音商城看这件"}
        </button>
        <PixelButton
          className="w-full"
          disabled={inCombo}
          onClick={() => onAddToCombo(item.id)}
        >
          {inCombo ? "✓ 已在衣柜里" : "🚪 放进衣柜组合"}
        </PixelButton>
      </div>
    </div>
  );
}
