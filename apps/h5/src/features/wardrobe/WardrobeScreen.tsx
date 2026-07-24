import { useMemo, useState } from "react";

import type { Item } from "../../api/client";
import { PendingItemCard, type PendingItem, WardrobeItemCard } from "./ItemCard";

type Filter = "all" | "owned" | "inspiration";

export function WardrobeScreen({
  items,
  pending,
  loading,
  onOpen,
  onRetry
}: {
  items: Item[];
  pending: PendingItem[];
  loading: boolean;
  onOpen: (item: Item) => void;
  onRetry: (item: Item) => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const visible = useMemo(
    () => (filter === "all" ? items : items.filter((item) => item.ownership === filter)),
    [filter, items]
  );
  const empty = !loading && visible.length === 0 && pending.length === 0;

  return (
    <section className="wardrobe-section" aria-labelledby="wardrobe-title">
      <div className="section-heading">
        <div>
          <p className="section-kicker">数字资产</p>
          <h2 id="wardrobe-title">我的收藏</h2>
        </div>
        <span className="item-count">{items.length + pending.length} 件</span>
      </div>

      <div className="filter-tabs" aria-label="筛选衣橱">
        {(
          [
            ["all", "全部"],
            ["owned", "我的衣服"],
            ["inspiration", "穿搭灵感"]
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={filter === value ? "is-selected" : ""}
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="wardrobe-loading" aria-label="正在加载衣橱">
          <span />
          <span />
        </div>
      ) : null}

      {empty ? (
        <div className="wardrobe-empty">
          <div className="empty-avatar">
            <img src="/assets/char-default.png" alt="" />
          </div>
          <h3>衣橱正在等第一件单品</h3>
          <p>从相册选一张，或直接拍下衣柜里的衣服。</p>
        </div>
      ) : (
        <div className="wardrobe-grid">
          {pending.map((entry) => (
            <PendingItemCard key={entry.jobId} pending={entry} />
          ))}
          {visible.map((item) => (
            <WardrobeItemCard
              key={item.id}
              item={item}
              onOpen={() => onOpen(item)}
              onRetry={() => onRetry(item)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
