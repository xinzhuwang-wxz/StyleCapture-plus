import { motion } from "motion/react";

import type { Look, RenderArtifact } from "../../api/client";

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
      className="item-card look-card"
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <button className="item-card__open" type="button" onClick={onOpen}>
        <div className="item-card__image look-card__image">
          {pixelCover?.output_image_url ? (
            <img src={pixelCover.output_image_url} alt="已生成的像素穿搭封面" />
          ) : look.display_image_url ? (
            <img src={look.display_image_url} alt="收藏的整套穿搭" />
          ) : (
            <div className="item-image-placeholder">
              <span>✦</span>
              <small>整套已保存，封面生成中</small>
            </div>
          )}
          <span className={`status-badge status-badge--${look.status}`}>
            {STATUS_LABELS[look.status]}
          </span>
          {look.status === "processing" ? (
            <div className="processing-sheen" aria-hidden="true" />
          ) : null}
          {pixelCover?.output_image_url ? (
            <span className="look-card__cover-label">像素封面</span>
          ) : null}
        </div>
        <div className="item-card__body">
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
