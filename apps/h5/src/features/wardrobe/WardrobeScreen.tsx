import { useMemo, useState } from "react";
import { motion } from "motion/react";
import {
  PixelBadge,
  PixelCard,
  PixelEmpty,
  PixelFilter,
  PixelSectionHeader
} from "../../components/PixelUI";
import { ShareModal } from "../../components/ShareModal";
import type { Item, Job, Ownership } from "../../api/client";

export type PendingItem = {
  captureId: string;
  jobId: string;
  previewUrl: string;
  ownership: Ownership;
  state: Job["state"];
};

type Filter = "all" | "owned" | "inspiration";

interface WardrobeScreenProps {
  items: Item[];
  pending: PendingItem[];
  loading: boolean;
  onOpenItem: (item: Item) => void;
  onOpenOutfit: (outfitId: string) => void;
  onRetry: (item: Item) => void;
}

const STATUS_LABELS: Record<Item["status"], string> = {
  processing: "识别中",
  partial: "待补全",
  ready: "可搭配",
  error: "失败"
};

const STATUS_EMOJI: Record<Item["status"], string> = {
  processing: "🔄",
  partial: "⚠️",
  ready: "✓",
  error: "✗"
};

function WardrobeItemCard({
  item,
  onOpen,
  onLongPress,
  onRetry
}: {
  item: Item;
  onOpen: () => void;
  onLongPress: () => void;
  onRetry: () => void;
}) {
  const category = String(
    item.attributes.subcategory?.value ??
      item.attributes.category?.value ??
      "待分类"
  );
  const isOwned = item.ownership === "owned";

  return (
    <PixelCard onClick={onOpen} onLongPress={onLongPress}>
      <PixelBadge variant={isOwned ? "star" : "heart"}>
        {isOwned ? "⭐" : "💖"}
      </PixelBadge>

      <div
        style={{
          position: "relative",
          aspectRatio: "0.82",
          background: isOwned
            ? "linear-gradient(145deg, #3d2b5e, #4d3b6e)"
            : "linear-gradient(145deg, #2d1b4e, #3d2b5e)",
          display: "grid",
          placeItems: "center"
        }}
      >
        <span style={{ fontSize: "3rem", filter: "grayscale(0.3)" }}>
          {isOwned ? "👕" : "💜"}
        </span>
        <span
          style={{
            position: "absolute",
            top: "var(--px-2)",
            left: "var(--px-2)",
            padding: "2px 6px",
            fontFamily: "var(--font-pixel)",
            fontSize: "0.6rem",
            background: "var(--pixel-surface)",
            border: "2px solid var(--pixel-border)",
            color:
              item.status === "ready"
                ? "var(--pixel-success)"
                : item.status === "error"
                  ? "var(--pixel-error)"
                  : "var(--pixel-warning)"
          }}
        >
          {STATUS_EMOJI[item.status]} {STATUS_LABELS[item.status]}
        </span>
      </div>

      <div style={{ padding: "var(--px-3)" }}>
        <strong
          style={{
            fontFamily: "var(--font-pixel)",
            fontSize: "0.8rem",
            color: "var(--pixel-text)",
            display: "block"
          }}
        >
          {category}
        </strong>
        <span
          style={{
            fontSize: "0.65rem",
            color: isOwned ? "var(--pixel-accent)" : "var(--pixel-primary)",
            fontFamily: "var(--font-pixel)"
          }}
        >
          {isOwned ? "⭐ 已拥有" : "💖 愿望单"}
        </span>
      </div>

      {(item.status === "error" || item.status === "partial") &&
      item.source_available ? (
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
            fontSize: "0.7rem",
            background: "var(--pixel-surface)",
            border: "2px solid var(--pixel-border)",
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

function PendingItemCard({ pending }: { pending: PendingItem }) {
  return (
    <motion.article
      className="pixel-card"
      layout
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <div
        style={{
          position: "relative",
          aspectRatio: "0.82",
          overflow: "hidden"
        }}
      >
        <img
          src={pending.previewUrl}
          alt="正在入库的衣服"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(0,0,0,0.4)",
            display: "grid",
            placeItems: "center"
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-pixel)",
              color: "#fff",
              fontSize: "0.8rem",
              textShadow: "2px 2px 0 rgba(0,0,0,0.5)"
            }}
          >
            🔄 处理中…
          </span>
        </div>
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: "4px",
            background: "var(--pixel-border)"
          }}
        >
          <motion.div
            style={{ height: "100%", background: "var(--pixel-primary)" }}
            animate={{ width: ["0%", "100%"] }}
            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
          />
        </div>
      </div>
      <div style={{ padding: "var(--px-3)" }}>
        <strong
          style={{
            fontFamily: "var(--font-pixel)",
            fontSize: "0.75rem",
            color: "var(--pixel-text-muted)"
          }}
        >
          正在理解这件衣服…
        </strong>
      </div>
    </motion.article>
  );
}

export function WardrobeScreen({
  items,
  pending,
  loading,
  onOpenItem,
  onOpenOutfit: _onOpenOutfit,
  onRetry
}: WardrobeScreenProps) {
  const [filter, setFilter] = useState<Filter>("all");
  const [shareItem, setShareItem] = useState<{
    imageUrl: string;
    title: string;
  } | null>(null);

  const visible = useMemo(
    () =>
      filter === "all"
        ? items
        : items.filter((item) => item.ownership === filter),
    [filter, items]
  );

  const empty = !loading && visible.length === 0 && pending.length === 0;

  const handleLongPress = (item: Item) => {
    const canvas = document.createElement("canvas");
    canvas.width = 400;
    canvas.height = 500;
    const ctx = canvas.getContext("2d")!;

    ctx.fillStyle = "#2d1b4e";
    ctx.fillRect(0, 0, 400, 500);

    ctx.strokeStyle = "#ff6b9d";
    ctx.lineWidth = 6;
    ctx.strokeRect(12, 12, 376, 476);

    ctx.fillStyle = "#3d2b5e";
    ctx.fillRect(100, 60, 200, 200);
    ctx.font = "80px serif";
    ctx.textAlign = "center";
    ctx.fillText(item.ownership === "owned" ? "⭐" : "💖", 200, 190);

    ctx.fillStyle = "#f3e8ff";
    ctx.font = "bold 24px 'Courier New', monospace";
    ctx.fillText(
      String(item.attributes.subcategory?.value ?? "单品"),
      200,
      320
    );
    ctx.font = "16px 'Courier New', monospace";
    ctx.fillStyle = "#a78bfa";
    ctx.fillText("StyleCapture 数字衣橱", 200, 370);
    ctx.fillText(
      item.ownership === "owned" ? "我的衣服" : "穿搭灵感",
      200,
      400
    );

    ctx.fillStyle = "#fbbf24";
    ctx.font = "20px 'Courier New', monospace";
    ctx.fillText("👾 StyleCapture+", 200, 460);

    setShareItem({
      imageUrl: canvas.toDataURL("image/png"),
      title: `分享：${String(item.attributes.subcategory?.value ?? "单品")}`
    });
  };

  return (
    <section aria-labelledby="wardrobe-title">
      <PixelSectionHeader
        kicker="数字资产"
        title="我的收藏"
        action={
          <span
            style={{
              fontFamily: "var(--font-pixel)",
              fontSize: "0.75rem",
              color: "var(--pixel-text-dim)"
            }}
          >
            {items.length + pending.length} 件
          </span>
        }
      />

      <PixelFilter
        options={[
          ["all", "全部"],
          ["owned", "已有"],
          ["inspiration", "未拥有"]
        ]}
        value={filter}
        onChange={setFilter}
      />

      {loading ? (
        <div className="pixel-loading" aria-label="正在加载衣橱">
          <div className="pixel-loading__skeleton" />
          <div className="pixel-loading__skeleton" />
          <div className="pixel-loading__skeleton" />
          <div className="pixel-loading__skeleton" />
        </div>
      ) : null}

      {empty ? (
        <PixelEmpty
          icon="👾"
          title="衣橱正在等第一件单品"
          description="从相册选一张，或直接拍下衣柜里的衣服。"
        />
      ) : (
        <div className="pixel-grid">
          {pending.map((entry) => (
            <PendingItemCard key={entry.jobId} pending={entry} />
          ))}
          {visible.map((item) => (
            <WardrobeItemCard
              key={item.id}
              item={item}
              onOpen={() => onOpenItem(item)}
              onLongPress={() => handleLongPress(item)}
              onRetry={() => onRetry(item)}
            />
          ))}
        </div>
      )}

      {shareItem ? (
        <ShareModal
          imageUrl={shareItem.imageUrl}
          title={shareItem.title}
          onClose={() => setShareItem(null)}
        />
      ) : null}
    </section>
  );
}
