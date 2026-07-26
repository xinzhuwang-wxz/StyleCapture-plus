import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import type { Item, Job, Ownership } from "../../api/client";
import { pixelGarmentIcon } from "../../utils/pixelAvatar";
import { garmentLabel } from "./localization";

export type PendingItem = {
  captureId: string;
  jobId: string;
  previewUrl: string | null;
  ownership: Ownership;
  state: Job["state"];
  errorCode?: string | null;
  errorMessage?: string | null;
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
      <DeferredPixelImage
        src={`${item.pixel_image_url}?v=${encodeURIComponent(item.updated_at)}`}
        alt={`${category}的像素展示图`}
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
      loading="lazy"
      decoding="async"
      data-image-kind="wardrobe-pixel-fallback"
      data-pixel="true"
    />
  );
}

function DeferredPixelImage({ src, alt }: { src: string; alt: string }) {
  const markerRef = useRef<HTMLSpanElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const marker = markerRef.current;
    if (!marker || visible) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        setVisible(true);
        observer.disconnect();
      },
      { rootMargin: "320px 0px" }
    );
    observer.observe(marker);
    return () => observer.disconnect();
  }, [visible]);

  return (
    <span ref={markerRef} className="wardrobe-card__deferred-image">
      {visible ? (
        <img
          src={src}
          alt={alt}
          loading="lazy"
          decoding="async"
          fetchPriority="low"
          data-image-kind="wardrobe-pixel"
          data-pixel="true"
        />
      ) : null}
    </span>
  );
}

export function WardrobeItemCard({
  item,
  onOpen,
  onRetry,
  onRetryPixel
}: {
  item: Item;
  onOpen: () => void;
  onRetry: () => void;
  onRetryPixel: () => void;
}) {
  const category = garmentLabel(
    item.attributes.subcategory?.value ?? item.attributes.category?.value
  );
  const description = String(item.attributes.description?.value ?? category);
  const ownershipLabel = item.ownership === "owned" ? "我的衣服" : "穿搭灵感";
  return (
    <motion.article
      className="item-card pixel-card wardrobe-card"
      data-item-id={item.id}
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
          ) : item.pixel_image_status === "failed" ? (
            <span className="item-card__pixel-status">像素图未生成</span>
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
      {item.pixel_image_status === "failed" ? (
        <button className="retry-link" type="button" onClick={onRetryPixel}>
          重试像素图
        </button>
      ) : null}
    </motion.article>
  );
}

function pendingFailureMessage(pending: PendingItem): string {
  if (pending.errorCode === "no_reliable_garment") {
    return "没有识别到清晰的衣服，请换一张主体更完整的照片";
  }
  if (pending.errorCode === "multiple_garments") {
    return "识别到多件衣服，请按“整套穿搭”重新保存";
  }
  return "这次没有识别成功，原图仍保留，可直接重试";
}

export function PendingItemCard({
  pending,
  onRetry,
  onDismiss
}: {
  pending: PendingItem;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  const failed = pending.state === "error";
  return (
    <motion.article
      className="item-card item-card--pending pixel-card wardrobe-card"
      layout
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <div className="item-card__image wardrobe-card__cover wardrobe-card__cover--item">
        {pending.previewUrl ? (
          <img
            src={pending.previewUrl}
            alt="正在入库的衣服"
            loading="lazy"
            decoding="async"
          />
        ) : (
          <div className="pending-heic-preview" role="status">
            <strong>正在转换 iPhone 照片</strong>
            <span>完成后会显示标准实物图</span>
          </div>
        )}
        <span
          className={`status-badge status-badge--${failed ? "error" : "processing"}`}
        >
          {failed ? "识别失败" : "后台处理中"}
        </span>
        {!failed ? <div className="processing-sheen" aria-hidden="true" /> : null}
      </div>
      <div className="item-card__body wardrobe-card__meta">
        <strong>{failed ? "这张照片暂时无法入库" : "正在理解这件衣服"}</strong>
        <span>
          {failed
            ? pendingFailureMessage(pending)
            : "可以继续浏览，完成后会自动出现"}
        </span>
        {failed ? (
          <div className="pending-item__actions">
            <button type="button" className="retry-link" onClick={onRetry}>
              重新识别
            </button>
            <button type="button" className="retry-link" onClick={onDismiss}>
              移除此条
            </button>
          </div>
        ) : null}
      </div>
    </motion.article>
  );
}
