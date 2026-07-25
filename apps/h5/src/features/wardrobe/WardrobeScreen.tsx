import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { motion } from "motion/react";

import { PixelEmpty, PixelFilter } from "../../components/PixelUI";
import type { Item, Job, Ownership } from "../../api/client";
import type { MockOutfit } from "../../mock/mockApi";
import { ComboBasketSheet, ComboWardrobe } from "./ComboWardrobe";
import { auditCombo } from "./comboRules";
import { ITEM_CATEGORIES, type CatalogItem } from "./catalog";
import { toDisplayItem } from "./displayItem";

export type PendingItem = {
  captureId: string;
  jobId: string;
  previewUrl: string;
  ownership: Ownership;
  state: Job["state"];
};

type Filter = "all" | "owned" | "inspiration";
type SubTab = "outfits" | "items";

const CATEGORY_TABS = ["全部", ...ITEM_CATEGORIES] as const;

/** 长按多久算「要拖动」而不是「点一下看详情」。 */
const LONG_PRESS_MS = 420;

const STYLE_CHIPS: Record<string, readonly [string, string]> = {
  复古: ["#ede9fe", "#7c5cd6"],
  甜美: ["#fce7f3", "#d1608f"],
  休闲: ["#e0f2fe", "#3f7fae"],
  简约: ["#fef3c7", "#a16207"],
  自由: ["#dcfce7", "#3f8a5f"]
};

interface WardrobeScreenProps {
  items: Item[];
  pending: PendingItem[];
  loading: boolean;
  outfits: MockOutfit[];
  onOpenItem: (itemId: string) => void;
  onOpenOutfit: (outfitId: string) => void;
  onSaveCombo: (itemIds: string[]) => Promise<void>;
  onRetry: (pending: PendingItem) => void;
  onNotice: (message: string) => void;
  /** 滚动区之外的悬浮层容器，悬浮衣柜和抽屉挂在这里 */
  overlayContainer: HTMLElement | null;
}

/** 衣橱里真实的 Item 列表，映射成展示模型。 */
function useDisplayItems(items: Item[]): CatalogItem[] {
  return useMemo(() => items.map(toDisplayItem), [items]);
}

// ─── 穿搭卡片（3:4 整套像素图）─────────────────────────────

function OutfitCard({ outfit, onOpen }: { outfit: MockOutfit; onOpen: () => void }) {
  const ownedCount = outfit.slots.filter((slot) => slot.owned).length;
  const [chipBg, chipFg] = STYLE_CHIPS[outfit.style] ?? ["#f0eaf9", "#7c6aa8"];

  return (
    <article className="pixel-card wardrobe-card" onClick={onOpen}>
      <div className="wardrobe-card__cover wardrobe-card__cover--outfit">
        {outfit.pixelCoverUrl ? (
          <img src={outfit.pixelCoverUrl} alt={outfit.name} data-pixel="true" />
        ) : (
          <div className="wardrobe-card__placeholder">
            🧩<span>拼贴封面</span>
          </div>
        )}
        <span className="wardrobe-card__ratio">3:4 整套</span>
        <span className="wardrobe-card__own">
          已有 {ownedCount}/{outfit.slots.length}
        </span>
        {/* 收藏只保留左上角五角星，右下角的爱心已移除（功能重合） */}
        {outfit.favorited ? (
          <span className="wardrobe-card__star" aria-label="已收藏">
            ⭐
          </span>
        ) : null}
      </div>
      <div className="wardrobe-card__meta">
        <strong>{outfit.name}</strong>
        <span className="wardrobe-card__chip" style={{ background: chipBg, color: chipFg }}>
          {outfit.style} · {outfit.scene}
        </span>
      </div>
    </article>
  );
}

// ─── 单品卡片（1:1，单击进详情 / 长按拖进衣柜）────────────────

function ItemCard({
  item,
  selected,
  onOpen,
  onLongPress
}: {
  item: CatalogItem;
  selected: boolean;
  onOpen: () => void;
  onLongPress: (point: { x: number; y: number }) => void;
}) {
  const timer = useRef<number | null>(null);
  const longPressed = useRef(false);

  const clear = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => clear, [clear]);

  return (
    <article
      className="pixel-card wardrobe-card"
      data-selected={selected ? "true" : undefined}
      // touch-action: pan-y 让纵向滚动照常，长按仍由计时器触发
      style={{ touchAction: "pan-y", userSelect: "none" }}
      onContextMenu={(event) => event.preventDefault()}
      onPointerDown={(event) => {
        const { clientX, clientY } = event;
        // 阻止浏览器把按住图片当成原生拖拽 —— 那会发出 pointercancel，
        // 把长按拖进衣柜的手势打断。
        event.preventDefault();
        longPressed.current = false;
        clear();
        timer.current = window.setTimeout(() => {
          longPressed.current = true;
          onLongPress({ x: clientX, y: clientY });
        }, LONG_PRESS_MS);
      }}
      onPointerUp={() => {
        clear();
        if (!longPressed.current) onOpen();
      }}
      onPointerLeave={clear}
    >
      <div className="wardrobe-card__cover wardrobe-card__cover--item">
        <img
          src={item.imageUrl}
          alt={item.name}
          data-pixel="true"
          draggable={false}
          style={{ filter: item.owned ? "none" : "grayscale(0.45) opacity(0.9)" }}
        />
        <span className="wardrobe-card__ratio">1:1 单品</span>
      </div>
      <div className="wardrobe-card__meta">
        <strong>{item.name}</strong>
        <div className="wardrobe-card__row">
          <span
            className="wardrobe-card__chip"
            style={
              item.owned
                ? { background: "#dcfce7", color: "#3f8a5f" }
                : { background: "#fce7f3", color: "#d1608f" }
            }
          >
            {item.owned ? "⭐ 已拥有" : `¥${item.price}`}
          </span>
          <span className="wardrobe-card__source">
            {item.owned ? "我的衣橱" : "抖音商城 ›"}
          </span>
        </div>
      </div>
    </article>
  );
}

// ─── 入库处理中卡片 ─────────────────────────────────────

function PendingItemCard({
  pending,
  onRetry
}: {
  pending: PendingItem;
  onRetry: () => void;
}) {
  const failed = pending.state === "error" || pending.state === "partial";

  return (
    <motion.article
      className="pixel-card"
      layout
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <div style={{ position: "relative", aspectRatio: "1" }}>
        <img
          src={pending.previewUrl}
          alt="正在入库的衣服"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(61,44,94,0.45)",
            display: "grid",
            placeItems: "center"
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-pixel)",
              color: "#fff",
              fontSize: "0.75rem",
              textAlign: "center",
              padding: "0 var(--px-2)"
            }}
          >
            {failed ? "⚠️ 这件没认出来" : "🔄 正在理解这件衣服…"}
          </span>
        </div>
        {failed ? null : (
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              height: "4px",
              background: "var(--pixel-border-light)"
            }}
          >
            <motion.div
              style={{ height: "100%", background: "var(--pixel-primary)" }}
              animate={{ width: ["0%", "100%"] }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            />
          </div>
        )}
      </div>
      {failed ? (
        <button type="button" className="wardrobe-card__retry" onClick={onRetry}>
          🔄 重新识别
        </button>
      ) : null}
    </motion.article>
  );
}

// ─── 衣橱主屏 ───────────────────────────────────────────

export function WardrobeScreen({
  items,
  pending,
  loading,
  outfits,
  onOpenItem,
  onOpenOutfit,
  onSaveCombo,
  onRetry,
  onNotice,
  overlayContainer
}: WardrobeScreenProps) {
  const [subTab, setSubTab] = useState<SubTab>("outfits");
  const [filter, setFilter] = useState<Filter>("all");
  const [category, setCategory] = useState<string>("全部");

  const [basket, setBasket] = useState<string[]>([]);
  const [basketOpen, setBasketOpen] = useState(false);
  const [doorOpen, setDoorOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [drag, setDrag] = useState<{ item: CatalogItem; x: number; y: number } | null>(null);
  const [overWardrobe, setOverWardrobe] = useState(false);

  const wardrobeRef = useRef<HTMLButtonElement>(null);
  const displayItems = useDisplayItems(items);

  const visibleItems = useMemo(
    () =>
      displayItems
        .filter((item) =>
          filter === "all" ? true : filter === "owned" ? item.owned : !item.owned
        )
        .filter((item) => category === "全部" || item.category === category),
    [displayItems, filter, category]
  );

  const visibleOutfits = useMemo(
    () =>
      outfits.filter((outfit) => {
        if (filter === "all") return true;
        const allOwned = outfit.slots.every((slot) => slot.owned);
        return filter === "owned" ? allOwned : !allOwned;
      }),
    [outfits, filter]
  );

  const basketItems = useMemo(
    () =>
      basket
        .map((id) => displayItems.find((item) => item.id === id))
        .filter((item): item is CatalogItem => Boolean(item)),
    [basket, displayItems]
  );

  /**
   * 提示语在这里先算好再 setState —— 放进 setBasket 的 updater 里会在 React
   * 渲染阶段更新父组件（App 的 toast），触发 "Cannot update a component while
   * rendering a different component" 警告。
   */
  const addToBasket = useCallback(
    (item: CatalogItem) => {
      const already = basket.includes(item.id);
      if (already) {
        onNotice("这件已经在衣柜里啦～");
        return;
      }
      setBasket((current) =>
        current.includes(item.id) ? current : [...current, item.id]
      );
      onNotice(`已放进衣柜 🚪 共 ${basket.length + 1} 件`);
      // 柜门开一下再自动关上
      setDoorOpen(true);
      window.setTimeout(() => setDoorOpen(false), 900);
    },
    [basket, onNotice]
  );

  const hitsWardrobe = useCallback((x: number, y: number) => {
    const element = wardrobeRef.current;
    if (!element) return false;
    const rect = element.getBoundingClientRect();
    const slack = 26;
    return (
      x > rect.left - slack &&
      x < rect.right + slack &&
      y > rect.top - slack &&
      y < rect.bottom + slack
    );
  }, []);

  // 拖动过程挂在 window 上，手指移出卡片也能继续跟手
  useEffect(() => {
    if (!drag) return;

    const move = (event: PointerEvent) => {
      event.preventDefault();
      setDrag((current) =>
        current ? { ...current, x: event.clientX, y: event.clientY } : current
      );
      setOverWardrobe(hitsWardrobe(event.clientX, event.clientY));
    };

    // effect 的依赖里有 drag，所以这个闭包里的 drag 一定是最新的一次拖动
    const drop = (event: PointerEvent) => {
      const landed = hitsWardrobe(event.clientX, event.clientY);
      setDrag(null);
      setOverWardrobe(false);
      if (landed) addToBasket(drag.item);
      else onNotice("松手时没落进衣柜，再来一次～");
    };

    window.addEventListener("pointermove", move, { passive: false });
    window.addEventListener("pointerup", drop);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", drop);
    };
  }, [drag, hitsWardrobe, addToBasket, onNotice]);

  const saveCombo = useCallback(async () => {
    const audit = auditCombo(basketItems);
    if (!audit.ok) {
      onNotice(`AI 审核没过：${audit.reason}`);
      return;
    }
    setSaving(true);
    try {
      await onSaveCombo(basketItems.map((item) => item.id));
      setBasket([]);
      setBasketOpen(false);
    } finally {
      setSaving(false);
    }
  }, [basketItems, onSaveCombo, onNotice]);

  const showEmpty =
    !loading &&
    pending.length === 0 &&
    (subTab === "items" ? visibleItems.length === 0 : visibleOutfits.length === 0);

  return (
    <section aria-labelledby="wardrobe-title">
      <div className="pixel-subtabs" role="tablist" aria-label="衣橱展示方式">
        <button
          type="button"
          role="tab"
          aria-selected={subTab === "outfits"}
          className={subTab === "outfits" ? "is-selected" : ""}
          onClick={() => setSubTab("outfits")}
        >
          👗 按穿搭
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={subTab === "items"}
          className={subTab === "items" ? "is-selected" : ""}
          onClick={() => setSubTab("items")}
        >
          👕 按单品
        </button>
      </div>

      <PixelFilter
        options={[
          ["all", "全部"],
          ["owned", "已有"],
          ["inspiration", "未拥有"]
        ]}
        value={filter}
        onChange={setFilter}
      />

      {subTab === "items" ? (
        <div className="pixel-chips" role="group" aria-label="单品分类">
          {CATEGORY_TABS.map((name) => (
            <button
              key={name}
              type="button"
              className={category === name ? "is-selected" : ""}
              onClick={() => setCategory(name)}
            >
              {name}
            </button>
          ))}
        </div>
      ) : null}

      {loading ? (
        <div className="pixel-loading" aria-label="正在加载衣橱">
          <div className="pixel-loading__skeleton" />
          <div className="pixel-loading__skeleton" />
          <div className="pixel-loading__skeleton" />
          <div className="pixel-loading__skeleton" />
        </div>
      ) : null}

      {showEmpty ? (
        <PixelEmpty
          icon="👾"
          title={subTab === "items" ? "这个分类还没有单品" : "还没有收藏穿搭"}
          description="去 Feed 里圈选一套，或让 AI 帮你搭三套。"
        />
      ) : (
        <div className="pixel-grid">
          {subTab === "items" ? (
            <>
              {pending.map((entry) => (
                <PendingItemCard
                  key={entry.jobId}
                  pending={entry}
                  onRetry={() => onRetry(entry)}
                />
              ))}
              {visibleItems.map((item) => (
                <ItemCard
                  key={item.id}
                  item={item}
                  selected={basket.includes(item.id)}
                  onOpen={() => onOpenItem(item.id)}
                  onLongPress={(point) => setDrag({ item, x: point.x, y: point.y })}
                />
              ))}
            </>
          ) : (
            visibleOutfits.map((outfit) => (
              <OutfitCard
                key={outfit.id}
                outfit={outfit}
                onOpen={() => onOpenOutfit(outfit.id)}
              />
            ))
          )}
        </div>
      )}

      {overlayContainer
        ? createPortal(
            <>
              {subTab === "items" ? (
                <ComboWardrobe
                  count={basket.length}
                  doorOpen={doorOpen}
                  highlighted={overWardrobe}
                  onOpen={() => setBasketOpen(true)}
                  wardrobeRef={wardrobeRef}
                />
              ) : null}

              {drag ? (
                <img
                  className="combo-drag-ghost"
                  src={drag.item.imageUrl}
                  alt=""
                  data-pixel="true"
                  style={{ left: `${drag.x - 34}px`, top: `${drag.y - 34}px` }}
                />
              ) : null}

              {basketOpen ? (
                <ComboBasketSheet
                  items={basketItems}
                  busy={saving}
                  onRemove={(itemId) =>
                    setBasket((current) => current.filter((id) => id !== itemId))
                  }
                  onClear={() => setBasket([])}
                  onSave={() => void saveCombo()}
                  onClose={() => setBasketOpen(false)}
                />
              ) : null}
            </>,
            overlayContainer
          )
        : null}
    </section>
  );
}
