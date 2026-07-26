import { motion } from "motion/react";

import type { Look, RenderArtifact } from "../../api/client";
import { pixelAvatarDataUrl } from "../../utils/pixelAvatar";

const STATUS_LABELS: Record<Look["status"], string> = {
  processing: "正在拆解",
  partial: "已收藏 · 待补全",
  ready: "搭配已解析",
  error: "解析失败"
};

export function LookCard({
  look,
  pixelCover = null,
  onOpen
}: {
  look: Look;
  pixelCover?: RenderArtifact | null;
  onOpen: () => void;
}) {
  const coverReady =
    pixelCover?.status === "succeeded" && Boolean(pixelCover.output_image_url);
  const coverFailed =
    pixelCover?.status === "failed" || pixelCover?.status === "degraded";
  const coverAlt = coverFailed
    ? "像素穿搭封面生成失败，当前显示临时像素形象"
    : "像素穿搭封面生成中";
  return (
    <motion.article
      className="item-card look-card pixel-card wardrobe-card"
      data-look-id={look.id}
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <button className="item-card__open" type="button" onClick={onOpen}>
        <div className="item-card__image look-card__image wardrobe-card__cover wardrobe-card__cover--outfit">
          {coverReady ? (
            <img
              src={pixelCover.output_image_url!}
              alt="已生成的像素穿搭封面"
              loading="lazy"
              decoding="async"
              data-image-kind="look-pixel-cover"
            />
          ) : (
            <img
              src={pixelAvatarDataUrl(look.id, { size: 300 })}
              alt={coverAlt}
              loading="lazy"
              decoding="async"
              data-image-kind="look-pixel-pending"
              data-pixel="true"
            />
          )}
          <span className={`status-badge status-badge--${look.status}`}>
            {STATUS_LABELS[look.status]}
          </span>
          {look.status === "processing" ? (
            <div className="processing-sheen" aria-hidden="true" />
          ) : null}
          {coverReady ? (
            <span className="look-card__cover-label">像素封面</span>
          ) : (
            <span className="look-card__cover-label">
              {coverFailed ? "生成失败 · 点开重试" : "生成中"}
            </span>
          )}
        </div>
        <div className="item-card__body wardrobe-card__meta">
          <strong>{look.source === "feed_saved" ? "Feed 穿搭灵感" : "我的搭配"}</strong>
          <span>
            {coverFailed
              ? "真实单品仍可查看，点开可重新生成封面"
              : look.status === "ready"
                ? "查看真实单品与搭配关系"
                : "原始穿搭已保存，AI 在后台理解"}
          </span>
        </div>
      </button>
    </motion.article>
  );
}
