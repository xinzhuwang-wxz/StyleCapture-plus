import { motion } from "motion/react";

import type { Look } from "../../api/client";

const STATUS_LABELS: Record<Look["status"], string> = {
  processing: "正在拆解",
  partial: "已收藏 · 待补全",
  ready: "搭配已解析",
  error: "解析失败"
};

export function LookCard({
  look,
  onOpen
}: {
  look: Look;
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
          {look.display_image_url ? (
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
