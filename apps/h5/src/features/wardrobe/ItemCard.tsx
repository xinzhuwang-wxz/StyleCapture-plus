import { motion } from "motion/react";

import type { Item, Job, Ownership } from "../../api/client";
import { garmentLabel } from "./localization";
import { useDisplayImage } from "./useDisplayImage";

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

function ItemImage({ item }: { item: Item }) {
  const imageUrl = useDisplayImage(item.id, `${item.status}:${item.updated_at}`);
  return imageUrl ? (
    <img
      src={imageUrl}
      alt={String(item.attributes.description?.value ?? "衣橱单品")}
      data-image-kind="wardrobe-display"
    />
  ) : (
    <div className="item-image-placeholder" aria-label="原图不可用">
      <span>衣</span>
    </div>
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
  return (
    <motion.article
      className="item-card"
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <button className="item-card__open" type="button" onClick={onOpen}>
        <div className="item-card__image">
          <ItemImage item={item} />
          <span className={`status-badge status-badge--${item.status}`}>
            {STATUS_LABELS[item.status]}
          </span>
        </div>
        <div className="item-card__body">
          <strong>{category}</strong>
          <span>{item.ownership === "owned" ? "我的衣服" : "穿搭灵感"}</span>
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
      className="item-card item-card--pending"
      layout
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <div className="item-card__image">
        <img src={pending.previewUrl} alt="正在入库的衣服" />
        <span className="status-badge status-badge--processing">后台处理中</span>
        <div className="processing-sheen" aria-hidden="true" />
      </div>
      <div className="item-card__body">
        <strong>正在理解这件衣服</strong>
        <span>可以继续浏览，完成后会自动出现</span>
      </div>
    </motion.article>
  );
}
