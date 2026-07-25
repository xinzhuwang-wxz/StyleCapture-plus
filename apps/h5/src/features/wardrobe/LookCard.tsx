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
  return (
    <motion.article
      className="item-card look-card pixel-card wardrobe-card"
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <button className="item-card__open" type="button" onClick={onOpen}>
        <div className="item-card__image look-card__image wardrobe-card__cover wardrobe-card__cover--outfit">
          {pixelCover?.output_image_url ? (
            <img
              src={pixelCover.output_image_url}
              alt="已生成的像素穿搭封面"
              data-image-kind="look-pixel-cover"
            />
          ) : (
            <img
              src={pixelAvatarDataUrl(look.id, { size: 300 })}
              alt="像素穿搭封面生成中"
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
          {pixelCover?.output_image_url ? (
            <span className="look-card__cover-label">像素封面</span>
          ) : (
            <span className="look-card__cover-label">生成中</span>
          )}
        </div>
        <div className="item-card__body wardrobe-card__meta">
          <strong>{look.source === "feed_saved" ? "Feed 穿搭灵感" : "我的搭配"}</strong>
          <span>
            {look.status === "ready"
              ? "查看真实单品与搭配关系"
              : "原始穿搭已保存，AI 在后台理解"}
          </span>
        </div>
      </button>
    </motion.article>
  );
}
