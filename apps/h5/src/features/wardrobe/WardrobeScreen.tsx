import { useMemo, useState } from "react";
import { motion } from "motion/react";
import {
  PixelBadge,
  PixelCard,
  PixelEmpty,
  PixelFilter
} from "../../components/PixelUI";
import { ShareModal } from "../../components/ShareModal";
import type { Item, Job, Ownership } from "../../api/client";
import type { MockOutfit } from "../../mock/mockApi";
import {
  buildShareCard,
  pixelAvatarDataUrl,
  pixelGarmentIcon
} from "../../utils/pixelAvatar";

export type PendingItem = {
  captureId: string;
  jobId: string;
  previewUrl: string;
  ownership: Ownership;
  state: Job["state"];
};

type Filter = "all" | "owned" | "inspiration";
type SubTab = "outfits" | "items";

const CATEGORIES = ["全部", "帽子", "上装", "外套", "连衣裙", "下装", "鞋子", "包包", "配饰"] as const;

interface WardrobeScreenProps {
  items: Item[];
  pending: PendingItem[];
  loading: boolean;
  outfits: MockOutfit[];
  onOpenItem: (item: Item) => void;
  onOpenOutfit: (outfitId: string) => void;
  onRetry: (item: Item) => void;
}

// ─── 单品卡片（像素预览 + 角标）─────────────────────────

function WardrobeItemCard({
  item,
  index,
  onOpen,
  onLongPress,
  onRetry
}: {
  item: Item;
  index: number;
  onOpen: () => void;
  onLongPress: () => void;
  onRetry: () => void;
}) {
  const category = String(item.attributes.category?.value ?? "配饰");
  const subcategory = String(
    item.attributes.subcategory?.value ?? category ?? "待分类"
  );
  const isOwned = item.ownership === "owned";
  const tall = index % 3 === 0;

  return (
    <PixelCard onClick={onOpen} onLongPress={onLongPress} className="wardrobe-masonry-card">
      <PixelBadge variant={isOwned ? "star" : "heart"}>
        {isOwned ? "⭐" : "💖"}
      </PixelBadge>

      <div
        style={{
          position: "relative",
          aspectRatio: tall ? "0.85" : "1.05",
          background: isOwned
            ? "linear-gradient(150deg, #f5edfb, #ede4fa)"
            : "linear-gradient(150deg, #efedf3, #e6e3ee)",
          display: "grid",
          placeItems: "center",
          padding: "var(--px-4)"
        }}
      >
        <img
          src={pixelGarmentIcon(category, { owned: isOwned, size: 140 })}
          alt={subcategory}
          data-pixel="true"
          style={{
            width: "72%",
            filter: isOwned ? "none" : "grayscale(0.6) opacity(0.75)"
          }}
        />
        {item.status === "processing" ? (
          <span
            style={{
              position: "absolute",
              bottom: "var(--px-2)",
              left: "var(--px-2)",
              padding: "2px 8px",
              fontFamily: "var(--font-pixel)",
              fontSize: "0.6rem",
              background: "#fff",
              borderRadius: "999px",
              border: "1px solid var(--pixel-border)",
              color: "var(--pixel-text-dim)"
            }}
          >
            🔄 识别中
          </span>
        ) : null}
      </div>

      <div style={{ padding: "var(--px-3)" }}>
        <strong
          style={{
            fontFamily: "var(--font-pixel)",
            fontSize: "0.82rem",
            color: "var(--pixel-text)",
            display: "block"
          }}
        >
          {subcategory}
        </strong>
        <span
          style={{
            fontSize: "0.62rem",
            color: isOwned ? "var(--pixel-accent-glow)" : "var(--pixel-pink-dark)",
            fontFamily: "var(--font-pixel)"
          }}
        >
          {isOwned ? "⭐ 已有" : "💖 未拥有"}
        </span>
      </div>

      {(item.status === "error" || item.status === "partial") && item.source_available ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRetry();
          }}
          style={{
            width: "calc(100% - var(--px-6))",
            margin: "0 var(--px-3) var(--px-3)",
            padding: "var(--px-2)",
            fontFamily: "var(--font-pixel)",
            fontSize: "0.68rem",
            background: "var(--pixel-bg)",
            border: "2px solid var(--pixel-border)",
            borderRadius: "999px",
            color: "var(--pixel-text-muted)",
            cursor: "pointer"
          }}
        >
          🔄 重新识别
        </button>
      ) : null}
    </PixelCard>
  );
}

// ─── 穿搭卡片（像素小人预览）────────────────────────────

function OutfitCard({
  outfit,
  index,
  onOpen,
  onLongPress
}: {
  outfit: MockOutfit;
  index: number;
  onOpen: () => void;
  onLongPress: () => void;
}) {
  const ownedCount = outfit.slots.filter((s) => s.owned).length;
  const allOwned = ownedCount === outfit.slots.length;
  const tall = index % 3 === 1;

  return (
    <PixelCard onClick={onOpen} onLongPress={onLongPress} className="wardrobe-masonry-card">
      <PixelBadge variant={allOwned ? "star" : "heart"}>
        {allOwned ? "⭐" : "💖"}
      </PixelBadge>
      <div
        style={{
          position: "relative",
          aspectRatio: tall ? "0.8" : "1",
          background: "linear-gradient(160deg, #faf5ff, #fdeef5)",
          display: "grid",
          placeItems: "center",
          padding: "var(--px-3)"
        }}
      >
        <img
          src={pixelAvatarDataUrl(outfit.seed, { size: 220 })}
          alt={outfit.name}
          data-pixel="true"
          style={{ width: "88%", borderRadius: "12px" }}
        />
      </div>
      <div style={{ padding: "var(--px-3)" }}>
        <strong
          style={{
            fontFamily: "var(--font-pixel)",
            fontSize: "0.8rem",
            color: "var(--pixel-text)",
            display: "block",
            lineHeight: 1.35
          }}
        >
          {outfit.name}
        </strong>
        <span
          style={{
            fontSize: "0.62rem",
            color: "var(--pixel-text-dim)",
            fontFamily: "var(--font-pixel)"
          }}
        >
          {outfit.style} · 已有 {ownedCount}/{outfit.slots.length} 件
        </span>
      </div>
    </PixelCard>
  );
}

// ─── 入库处理中卡片 ─────────────────────────────────────

function PendingItemCard({ pending }: { pending: PendingItem }) {
  return (
    <motion.article
      className="pixel-card wardrobe-masonry-card"
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
              fontSize: "0.8rem"
            }}
          >
            🔄 正在理解这件衣服…
          </span>
        </div>
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
      </div>
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
  onRetry
}: WardrobeScreenProps) {
  const [subTab, setSubTab] = useState<SubTab>("outfits");
  const [filter, setFilter] = useState<Filter>("all");
  const [category, setCategory] = useState<string>("全部");
  const [share, setShare] = useState<{ imageUrl: string; title: string } | null>(null);

  const visibleItems = useMemo(
    () =>
      items
        .filter((item) => filter === "all" || item.ownership === filter)
        .filter(
          (item) =>
            category === "全部" ||
            String(item.attributes.category?.value ?? "") === category
        ),
    [items, filter, category]
  );

  const visibleOutfits = useMemo(
    () =>
      outfits.filter((outfit) => {
        if (filter === "all") return true;
        const allOwned = outfit.slots.every((s) => s.owned);
        return filter === "owned" ? allOwned : !allOwned;
      }),
    [outfits, filter]
  );

  const shareItem = (item: Item) => {
    const name = String(item.attributes.subcategory?.value ?? "单品");
    setShare({
      imageUrl: buildShareCard({
        seed: item.id,
        title: name,
        subtitle: item.ownership === "owned" ? "我的已有单品" : "心动收藏单品",
        badge: item.ownership === "owned" ? "star" : "heart"
      }),
      title: `分享：${name}`
    });
  };

  const shareOutfit = (outfit: MockOutfit) => {
    setShare({
      imageUrl: buildShareCard({
        seed: outfit.seed,
        title: outfit.name,
        subtitle: `${outfit.style} · ${outfit.scene}`,
        badge: outfit.slots.every((s) => s.owned) ? "star" : "heart"
      }),
      title: `分享：${outfit.name}`
    });
  };

  const showEmpty =
    !loading &&
    pending.length === 0 &&
    (subTab === "items" ? visibleItems.length === 0 : visibleOutfits.length === 0);

  return (
    <section aria-labelledby="wardrobe-title">
      {/* 穿搭 / 单品 子页签 */}
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

      {/* 拥有状态筛选 */}
      <PixelFilter
        options={[
          ["all", "全部"],
          ["owned", "⭐ 已有"],
          ["inspiration", "💖 未拥有"]
        ]}
        value={filter}
        onChange={setFilter}
      />

      {/* 单品分类 */}
      {subTab === "items" ? (
        <div className="pixel-chips" role="group" aria-label="单品分类">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              type="button"
              className={category === c ? "is-selected" : ""}
              onClick={() => setCategory(c)}
            >
              {c}
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
        <div className="wardrobe-masonry">
          {subTab === "items" ? (
            <>
              {pending.map((entry) => (
                <PendingItemCard key={entry.jobId} pending={entry} />
              ))}
              {visibleItems.map((item, index) => (
                <WardrobeItemCard
                  key={item.id}
                  item={item}
                  index={index}
                  onOpen={() => onOpenItem(item)}
                  onLongPress={() => shareItem(item)}
                  onRetry={() => onRetry(item)}
                />
              ))}
            </>
          ) : (
            visibleOutfits.map((outfit, index) => (
              <OutfitCard
                key={outfit.id}
                outfit={outfit}
                index={index}
                onOpen={() => onOpenOutfit(outfit.id)}
                onLongPress={() => shareOutfit(outfit)}
              />
            ))
          )}
        </div>
      )}

      {share ? (
        <ShareModal
          imageUrl={share.imageUrl}
          title={share.title}
          onClose={() => setShare(null)}
        />
      ) : null}
    </section>
  );
}
