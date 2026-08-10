import { useEffect, useMemo, useRef, useState } from "react";

import type { Item, Look, RenderArtifact } from "../../api/client";
import { ComboBasket } from "../combo/ComboBasket";
import { ComboDetailSheet } from "../combo/ComboDetailSheet";
import {
  addToBasket,
  basketEntryOf,
  isInBasket,
  removeFromBasket,
  type BasketEntry
} from "../combo/basketRules";
import { ComboDraggableItem } from "../combo/ComboDraggableItem";
import { PendingItemCard, type PendingItem } from "./ItemCard";
import { LookCard } from "./LookCard";
import "./wardrobe.css";

type ItemFilter = "all" | "owned" | "inspiration";
type LookFilter = "all" | Look["source"];
export type WardrobeView = "looks" | "items";

const ITEM_FILTER_OPTIONS: readonly [ItemFilter, string][] = [
  ["all", "全部"],
  ["owned", "已拥有"],
  ["inspiration", "未拥有"]
];

const LOOK_FILTER_OPTIONS: readonly [LookFilter, string][] = [
  ["all", "全部"],
  ["user_created", "本地上传"],
  ["feed_saved", "灵感收藏"],
  ["ai_generated", "AI 推荐"]
];

export function WardrobeScreen({
  view,
  onViewChange,
  looks,
  pixelCovers,
  collageCovers,
  lookRenders = {},
  items,
  pending,
  itemsLoading,
  looksLoading,
  itemsError,
  looksError,
  itemsErrorDetail,
  looksErrorDetail,
  onRetryItems,
  onRetryLooks,
  onOpen,
  onOpenLook,
  onRetry,
  onRetryPixel,
  onRetryPending,
  onDismissPending,
  onSaveCombo,
  onNotice
}: {
  view: WardrobeView;
  onViewChange: (view: WardrobeView) => void;
  looks: Look[];
  pixelCovers: Record<string, RenderArtifact>;
  collageCovers: Record<string, RenderArtifact>;
  lookRenders?: Record<string, readonly RenderArtifact[]>;
  items: Item[];
  pending: PendingItem[];
  itemsLoading: boolean;
  looksLoading: boolean;
  itemsError: boolean;
  looksError: boolean;
  itemsErrorDetail?: string | null;
  looksErrorDetail?: string | null;
  onRetryItems: () => void;
  onRetryLooks: () => void;
  onOpen: (item: Item) => void;
  onOpenLook: (look: Look) => void;
  onRetry: (item: Item) => void;
  onRetryPixel: (item: Item) => void;
  onRetryPending: (pending: PendingItem) => void;
  onDismissPending: (pending: PendingItem) => void;
  /**
   * 存成穿搭。intent 决定存完接着生成什么——两者都由用户手动点，
   * 各要跑一次真实模型调用，不该自动触发。
   */
  onSaveCombo?: (
    entries: readonly BasketEntry[],
    intent: "cover" | "try_on"
  ) => Promise<void> | void;
  onNotice?: (message: string) => void;
}) {
  const [basket, setBasket] = useState<readonly BasketEntry[]>([]);
  const [basketOpen, setBasketOpen] = useState(false);
  const [receiving, setReceiving] = useState(false);
  const [savingCombo, setSavingCombo] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const filterMenuRef = useRef<HTMLDivElement>(null);

  function toggleInBasket(item: Item, label: string) {
    setBasket((current) => {
      if (isInBasket(current, item.id)) return removeFromBasket(current, item.id);
      const next = addToBasket(current, basketEntryOf(item, label));
      // 放进去只演一下柜门，不要抢着把二级页顶到脸上——进去看是点击才该
      // 发生的事，拖到一半被弹走反而没法接着拖下一件。
      if (next === current) onNotice?.("组合衣柜放满了，先拿出一件再加");
      return next;
    });
  }
  const [itemFilter, setItemFilter] = useState<ItemFilter>("all");
  const [lookFilter, setLookFilter] = useState<LookFilter>("all");
  const activeFilter = view === "looks" ? lookFilter : itemFilter;
  const activeFilterOptions =
    view === "looks" ? LOOK_FILTER_OPTIONS : ITEM_FILTER_OPTIONS;
  const filterLabel =
    activeFilterOptions.find(([value]) => value === activeFilter)?.[1] ?? "全部";
  useEffect(() => {
    if (view === "looks" && looks.length === 0 && items.length + pending.length > 0) {
      onViewChange("items");
    }
  }, [items.length, looks.length, onViewChange, pending.length, view]);
  useEffect(() => {
    if (!filterOpen) return;

    function closeOnOutsidePointer(event: PointerEvent) {
      if (!filterMenuRef.current?.contains(event.target as Node)) {
        setFilterOpen(false);
      }
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setFilterOpen(false);
    }

    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [filterOpen]);
  const visibleItems = useMemo(
    () =>
      itemFilter === "all"
        ? items
        : items.filter((item) => item.ownership === itemFilter),
    [itemFilter, items]
  );
  const visibleLooks = useMemo(
    () =>
      lookFilter === "all"
        ? looks
        : looks.filter((look) => look.source === lookFilter),
    [lookFilter, looks]
  );
  const loading = view === "looks" ? looksLoading : itemsLoading;
  const hasError = view === "looks" ? looksError : itemsError;
  const errorDetail = view === "looks" ? looksErrorDetail : itemsErrorDetail;
  const empty =
    !loading &&
    !hasError &&
    (view === "looks"
      ? visibleLooks.length === 0
      : visibleItems.length === 0 && pending.length === 0);
  const filterHasNoResults =
    activeFilter !== "all" &&
    (view === "looks" ? looks.length > 0 : items.length > 0);

  async function composeCombo(intent: "cover" | "try_on") {
    if (!onSaveCombo) {
      // 没接保存能力时说实话，而不是假装存好了。
      onNotice?.("这套组合还不能保存，稍后再试");
      return;
    }
    setSavingCombo(true);
    try {
      await onSaveCombo(basket, intent);
      setBasket([]);
      setBasketOpen(false);
    } finally {
      setSavingCombo(false);
    }
  }

  if (basketOpen) {
    return (
      <ComboDetailSheet
        basket={basket}
        busy={savingCombo}
        onRemove={(itemId) =>
          setBasket((current) => removeFromBasket(current, itemId))
        }
        onClear={() => setBasket([])}
        onCompose={() => void composeCombo("cover")}
        onTryOn={() => void composeCombo("try_on")}
        onClose={() => setBasketOpen(false)}
      />
    );
  }

  return (
    <section className="wardrobe-section" aria-labelledby="wardrobe-title">
      <div className="wardrobe-toolbar">
        <div className="wardrobe-view-tabs" aria-label="选择衣橱视图" role="tablist">
          <button
            type="button"
            className={view === "looks" ? "is-selected" : ""}
            aria-selected={view === "looks"}
            role="tab"
            onClick={() => {
              onViewChange("looks");
              setFilterOpen(false);
            }}
          >
            按穿搭
          </button>
          <button
            type="button"
            className={view === "items" ? "is-selected" : ""}
            aria-selected={view === "items"}
            role="tab"
            onClick={() => {
              onViewChange("items");
              setFilterOpen(false);
            }}
          >
            按单品
          </button>
        </div>

        <div className="wardrobe-filter" ref={filterMenuRef}>
            <button
              type="button"
              className={`wardrobe-filter__trigger${activeFilter !== "all" ? " is-active" : ""}`}
              aria-label={`${view === "looks" ? "筛选穿搭" : "筛选单品"}：${filterLabel}`}
              aria-haspopup="menu"
              aria-expanded={filterOpen}
              onClick={() => setFilterOpen((current) => !current)}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
                <path d="M4 6h16M7 12h10M10 18h4" />
              </svg>
            </button>

            {filterOpen ? (
              <div
                className="wardrobe-filter__menu"
                role="menu"
                aria-label={view === "looks" ? "筛选穿搭来源" : "筛选单品归属"}
              >
                {activeFilterOptions.map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    role="menuitemradio"
                    aria-checked={activeFilter === value}
                    className={activeFilter === value ? "is-selected" : ""}
                    onClick={() => {
                      if (view === "looks") {
                        setLookFilter(value as LookFilter);
                      } else {
                        setItemFilter(value as ItemFilter);
                      }
                      setFilterOpen(false);
                    }}
                  >
                    <span>{label}</span>
                    <span aria-hidden="true">{activeFilter === value ? "✓" : ""}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
      </div>

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
          {errorDetail ? (
            <p className="wardrobe-error-detail">诊断：{errorDetail}</p>
          ) : null}
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
          <h3>
            {filterHasNoResults
              ? view === "looks"
                ? "没有这个来源的穿搭"
                : "没有符合条件的单品"
              : view === "looks"
                ? "收藏一套喜欢的穿搭"
                : "衣橱正在等第一件单品"}
          </h3>
          <p>
            {filterHasNoResults
              ? "可以换一个筛选条件看看。"
              : view === "looks"
              ? "在 Feed 圈住整套并右滑，它会先完整保存，再在后台拆成单品。"
              : "从相册选一张，或直接拍下衣柜里的衣服。"}
          </p>
        </div>
      ) : !hasError ? (
        <div className="wardrobe-grid">
          {view === "looks"
            ? visibleLooks.map((look) => (
                <LookCard
                  key={look.id}
                  look={look}
                  pixelCover={pixelCovers[look.id] ?? null}
                  collageCover={collageCovers[look.id] ?? null}
                  renders={lookRenders[look.id] ?? []}
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
                {visibleItems.map((item) => (
                  <ComboDraggableItem
                    key={item.id}
                    item={item}
                    inBasket={isInBasket(basket, item.id)}
                    onOpen={() => onOpen(item)}
                    onRetry={() => onRetry(item)}
                    onRetryPixel={() => onRetryPixel(item)}
                    onToggleBasket={(label) => toggleInBasket(item, label)}
                    onDragActive={setReceiving}
                  />
                ))}
              </>}
        </div>
      ) : null}

      {view === "items" ? (
        <ComboBasket
          basket={basket}
          receiving={receiving}
          onOpen={() => setBasketOpen(true)}
        />
      ) : null}
    </section>
  );
}
