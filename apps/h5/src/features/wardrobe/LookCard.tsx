import { motion } from "motion/react";

import type { Look, RenderArtifact } from "../../api/client";
import { pixelAvatarDataUrl } from "../../utils/pixelAvatar";

const SOURCE_LABELS: Record<Look["source"], string> = {
  feed_saved: "灵感收藏",
  user_created: "本地上传",
  ai_generated: "AI 推荐"
};

export function LookCard({
  look,
  pixelCover = null,
  collageCover = null,
  renders = [],
  onOpen
}: {
  look: Look;
  pixelCover?: RenderArtifact | null;
  collageCover?: RenderArtifact | null;
  renders?: readonly RenderArtifact[];
  onOpen: () => void;
}) {
  const coverReady =
    pixelCover?.status === "succeeded" && Boolean(pixelCover.output_image_url);
  const coverFailed =
    pixelCover?.status === "failed" || pixelCover?.status === "degraded";
  const coverAlt = coverFailed
    ? "像素穿搭封面生成失败，当前显示临时像素形象"
    : "像素穿搭封面生成中";
  const collageReady =
    collageCover?.status === "succeeded" && Boolean(collageCover.output_image_url);
  const fallbackCoverUrl = collageReady
    ? collageCover.output_image_url
    : look.display_image_url ?? look.source_image_url;
  const hasInFlightCoverRender = renders.some(
    (render) =>
      (render.kind === "collage" || render.kind === "pixel_cover") &&
      (render.status === "queued" || render.status === "running")
  );
  const organizing =
    look.status !== "ready" || (!coverReady && hasInFlightCoverRender);
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
          ) : fallbackCoverUrl ? (
            <img
              className="look-card__fallback-cover"
              src={fallbackCoverUrl}
              alt="单品拼贴封面占位"
              loading="lazy"
              decoding="async"
              data-image-kind={collageReady ? "look-collage-placeholder" : "look-source-placeholder"}
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
          {organizing ? (
            <div className="processing-sheen" aria-hidden="true" />
          ) : null}
        </div>
        <div className="item-card__body wardrobe-card__meta">
          <strong>{look.display_name}</strong>
          <span>
            {SOURCE_LABELS[look.source]} · {organizing ? "正在整理" : "已整理"}
          </span>
        </div>
      </button>
    </motion.article>
  );
}
