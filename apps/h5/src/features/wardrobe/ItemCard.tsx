import { motion } from "motion/react";

import type { Item, Job, Ownership } from "../../api/client";
import { pixelGarmentIcon } from "../../utils/pixelAvatar";
import { garmentLabel } from "./localization";

export type PendingItem = {
  captureId: string;
  jobId: string;
  previewUrl: string;
  ownership: Ownership;
  state: Job["state"];
};

const STATUS_LABELS: Record<Item["status"], string> = {
  processing: "正在识别",
  partial: "已入库 · 待补全",
  ready: "可搭配",
  error: "识别失败"
};

function PixelItemImage({
  item,
  category
}: {
  item: Item;
  category: string;
}) {
  if (item.pixel_image_url) {
    return (
      <img
        src={`${item.pixel_image_url}?v=${encodeURIComponent(item.updated_at)}`}
        alt={`${category}的像素展示图`}
        data-image-kind="wardrobe-pixel"
        data-pixel="true"
      />
    );
  }
  return (
    <img
      src={pixelGarmentIcon(category, {
        size: 220,
        owned: item.ownership === "owned"
      })}
      alt={`${category}的像素图标`}
      data-image-kind="wardrobe-pixel-fallback"
      data-pixel="true"
    />
  );
}

export function WardrobeItemCard({
  item,
  onOpen,
  onRetry
}: {
  item: Item;
  onOpen: () => void;
  onRetry: () => void;
}) {
  const category = garmentLabel(
    item.attributes.subcategory?.value ?? item.attributes.category?.value
  );
  const description = String(item.attributes.description?.value ?? category);
  const ownershipLabel = item.ownership === "owned" ? "我的衣服" : "穿搭灵感";
  return (
    <motion.article
      className="item-card pixel-card wardrobe-card"
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <button
        aria-label={`${description} ${STATUS_LABELS[item.status]} ${category} ${ownershipLabel}`}
        className="item-card__open"
        type="button"
        onClick={onOpen}
      >
        <div className="item-card__image wardrobe-card__cover wardrobe-card__cover--item">
          <PixelItemImage item={item} category={category} />
          <span className={`status-badge status-badge--${item.status}`}>
            {STATUS_LABELS[item.status]}
          </span>
          {item.pixel_image_status === "queued" ||
          item.pixel_image_status === "running" ? (
            <span className="item-card__pixel-status">像素图生成中</span>
          ) : null}
        </div>
        <div className="item-card__body wardrobe-card__meta">
          <strong>{category}</strong>
          <span>{ownershipLabel} · 点开看真实图</span>
        </div>
      </button>
      {(item.status === "error" || item.status === "partial") &&
      item.source_available ? (
        <button className="retry-link" type="button" onClick={onRetry}>
          重新识别
        </button>
      ) : null}
    </motion.article>
  );
}

export function PendingItemCard({ pending }: { pending: PendingItem }) {
  return (
    <motion.article
      className="item-card item-card--pending pixel-card wardrobe-card"
      layout
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <div className="item-card__image wardrobe-card__cover wardrobe-card__cover--item">
        <img src={pending.previewUrl} alt="正在入库的衣服" />
        <span className="status-badge status-badge--processing">后台处理中</span>
        <div className="processing-sheen" aria-hidden="true" />
      </div>
      <div className="item-card__body wardrobe-card__meta">
        <strong>正在理解这件衣服</strong>
        <span>可以继续浏览，完成后会自动出现</span>
      </div>
    </motion.article>
  );
}
