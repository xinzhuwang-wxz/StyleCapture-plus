import { useEffect, useMemo, useState } from "react";

import type { Item, Look, RenderArtifact } from "../../api/client";
import { PendingItemCard, type PendingItem, WardrobeItemCard } from "./ItemCard";
import { LookCard } from "./LookCard";
import "./wardrobe.css";

type Filter = "all" | "owned" | "inspiration";
type WardrobeView = "looks" | "items";

export function WardrobeScreen({
  looks,
  pixelCovers,
  items,
  pending,
  itemsLoading,
  looksLoading,
  itemsError,
  looksError,
  onRetryItems,
  onRetryLooks,
  onOpen,
  onOpenLook,
  onRetry,
  onRetryPixel,
  onRetryPending,
  onDismissPending
}: {
  looks: Look[];
  pixelCovers: Record<string, RenderArtifact>;
  items: Item[];
  pending: PendingItem[];
  itemsLoading: boolean;
  looksLoading: boolean;
  itemsError: boolean;
  looksError: boolean;
  onRetryItems: () => void;
  onRetryLooks: () => void;
  onOpen: (item: Item) => void;
  onOpenLook: (look: Look) => void;
  onRetry: (item: Item) => void;
  onRetryPixel: (item: Item) => void;
  onRetryPending: (pending: PendingItem) => void;
  onDismissPending: (pending: PendingItem) => void;
}) {
  const [view, setView] = useState<WardrobeView>("looks");
  const [filter, setFilter] = useState<Filter>("all");
  useEffect(() => {
    if (view === "looks" && looks.length === 0 && items.length + pending.length > 0) {
      setView("items");
    }
  }, [items.length, looks.length, pending.length, view]);
  const visible = useMemo(
    () => (filter === "all" ? items : items.filter((item) => item.ownership === filter)),
    [filter, items]
  );
  const loading = view === "looks" ? looksLoading : itemsLoading;
  const hasError = view === "looks" ? looksError : itemsError;
  const empty =
    !loading &&
    !hasError &&
    (view === "looks"
      ? looks.length === 0
      : visible.length === 0 && pending.length === 0);

  return (
    <section className="wardrobe-section" aria-labelledby="wardrobe-title">
      <div className="section-heading">
        <div>
          <p className="section-kicker">数字资产</p>
          <h2 id="wardrobe-title">我的数字衣橱</h2>
        </div>
        <span className="item-count">
          {view === "looks" ? `${looks.length} 套` : `${items.length + pending.length} 件`}
        </span>
      </div>

      <div className="wardrobe-view-tabs" aria-label="选择衣橱视图" role="tablist">
        <button
          type="button"
          className={view === "looks" ? "is-selected" : ""}
          aria-selected={view === "looks"}
          role="tab"
          onClick={() => setView("looks")}
        >
          按穿搭
        </button>
        <button
          type="button"
          className={view === "items" ? "is-selected" : ""}
          aria-selected={view === "items"}
          role="tab"
          onClick={() => setView("items")}
        >
          按单品
        </button>
      </div>

      {view === "items" ? <div className="filter-tabs" aria-label="筛选衣橱">
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
            aria-pressed={filter === value}
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div> : null}

      {loading ? (
        <div className="wardrobe-loading" aria-label="正在加载衣橱">
          <span />
          <span />
        </div>
      ) : null}

      {hasError && !loading ? (
        <div className="wardrobe-empty wardrobe-empty--error" role="alert">
          <div className="empty-avatar">
            <img src="/assets/char-default.png" alt="" />
          </div>
          <h3>衣橱暂时未加载，已有数据没有丢失</h3>
          <p>
            {view === "looks"
              ? "穿搭列表读取失败。请重试加载，不会把已有套装显示成空衣橱。"
              : "单品列表读取失败。请重试加载，不会把已有单品显示成空衣橱。"}
          </p>
          <button
            type="button"
            className="wardrobe-error-retry"
            onClick={view === "looks" ? onRetryLooks : onRetryItems}
          >
            重新加载
          </button>
        </div>
      ) : null}

      {empty ? (
        <div className="wardrobe-empty">
          <div className="empty-avatar">
            <img src="/assets/char-default.png" alt="" />
          </div>
          <h3>{view === "looks" ? "收藏一套喜欢的穿搭" : "衣橱正在等第一件单品"}</h3>
          <p>
            {view === "looks"
              ? "在 Feed 圈住整套并右滑，它会先完整保存，再在后台拆成单品。"
              : "从相册选一张，或直接拍下衣柜里的衣服。"}
          </p>
        </div>
      ) : !hasError ? (
        <div className="wardrobe-grid">
          {view === "looks"
            ? looks.map((look) => (
                <LookCard
                  key={look.id}
                  look={look}
                  pixelCover={pixelCovers[look.id] ?? null}
                  onOpen={() => onOpenLook(look)}
                />
              ))
            : <>
                {pending.map((entry) => (
                  <PendingItemCard
                    key={entry.jobId}
                    pending={entry}
                    onRetry={() => onRetryPending(entry)}
                    onDismiss={() => onDismissPending(entry)}
                  />
                ))}
                {visible.map((item) => (
                  <WardrobeItemCard
                    key={item.id}
                    item={item}
                    onOpen={() => onOpen(item)}
                    onRetry={() => onRetry(item)}
                    onRetryPixel={() => onRetryPixel(item)}
                  />
                ))}
              </>}
        </div>
      ) : null}
    </section>
  );
}
