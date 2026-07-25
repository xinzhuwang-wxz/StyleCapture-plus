import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import type {
  LookDetail as LookDetailData,
  RenderArtifact,
  RenderKind
} from "../../api/client";

type LookDetailProps = {
  detail: LookDetailData | null;
  loading: boolean;
  renders?: RenderArtifact[];
  rendersLoading?: boolean;
  generatingKind?: RenderKind | null;
  retrying: boolean;
  saving: boolean;
  onClose: () => void;
  onReturnToSource: (videoRef: string, timestampMs: number) => void;
  onRetry: (lookId: string) => void;
  onSaveReason: (lookId: string, reason: string) => void;
  onGenerate?: (lookId: string, kind: RenderKind) => void;
};

function DetailContent({
  detail,
  renders = [],
  rendersLoading = false,
  generatingKind = null,
  retrying,
  saving,
  onClose,
  onReturnToSource,
  onRetry,
  onSaveReason,
  onGenerate
}: Omit<LookDetailProps, "detail" | "loading"> & {
  detail: LookDetailData;
}) {
  const [reason, setReason] = useState("");
  const [activeRenderKind, setActiveRenderKind] =
    useState<RenderKind>("collage");
  const [sharing, setSharing] = useState(false);
  const [shareMessage, setShareMessage] = useState<string | null>(null);
  const values = detail.analysis?.values ?? {};
  const heroImageUrl =
    detail.look.source_image_url ?? detail.look.display_image_url;

  useEffect(() => {
    setReason("");
    setActiveRenderKind("collage");
    setShareMessage(null);
  }, [detail.look.id]);

  useEffect(() => {
    if (generatingKind) setActiveRenderKind(generatingKind);
  }, [generatingKind]);

  const latestByKind = new Map<RenderKind, RenderArtifact>();
  [...renders]
    .sort((left, right) => right.updated_at.localeCompare(left.updated_at))
    .forEach((render) => {
      if (!latestByKind.has(render.kind)) latestByKind.set(render.kind, render);
    });
  const collage = latestByKind.get("collage");
  const activeRender = latestByKind.get(activeRenderKind);
  const visibleRender =
    activeRender?.output_image_url ? activeRender : collage;
  const pixelCover = latestByKind.get("pixel_cover");

  async function sharePixelCover() {
    if (!pixelCover?.share_eligible || !pixelCover.output_image_url) return;
    setSharing(true);
    setShareMessage(null);
    try {
      const response = await fetch(pixelCover.output_image_url, {
        cache: "no-store",
        credentials: "same-origin"
      });
      if (!response.ok) throw new Error("像素封面暂时无法读取");
      const blob = await response.blob();
      const file = new File([blob], `stylecapture-${detail.look.id}.png`, {
        type: blob.type || "image/png"
      });
      if (
        navigator.share &&
        (!navigator.canShare || navigator.canShare({ files: [file] }))
      ) {
        await navigator.share({
          files: [file],
          title: "我的 StyleCapture 穿搭",
          text: "把今天喜欢的穿搭收进数字衣橱"
        });
        setShareMessage("已打开系统分享");
      } else {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = file.name;
        link.click();
        URL.revokeObjectURL(url);
        setShareMessage("像素封面已下载");
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setShareMessage(error instanceof Error ? error.message : "分享没有完成");
    } finally {
      setSharing(false);
    }
  }

  return (
    <motion.section
      className="detail-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="look-detail-title"
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ type: "spring", stiffness: 340, damping: 36 }}
    >
      <div className="detail-topbar">
        <button className="icon-button" type="button" aria-label="返回衣橱" onClick={onClose}>
          ‹
        </button>
        <strong id="look-detail-title">穿搭详情</strong>
        <span className="detail-topbar__spacer" />
      </div>

      <div className="detail-image look-detail__hero">
        {heroImageUrl ? (
          <img
            src={heroImageUrl}
            alt="收藏的真实整套穿搭"
          />
        ) : (
          <div className="item-image-placeholder">
            <span>✦</span>
            <small>原始画面已删除</small>
          </div>
        )}
        {detail.look.status === "processing" ? (
          <div className="look-detail__processing">
            <strong>整套已收藏</strong>
            <span>AI 正在后台拆解真实单品</span>
          </div>
        ) : null}
      </div>

      <div className="detail-content">
        <div className="detail-meta">
          <span>
            {detail.look.source_available ? "真实 Feed 来源" : "来源画面已删除"}
          </span>
          <span>
            {detail.look.status === "ready" ? "搭配分析完成" : "后台处理中"}
          </span>
        </div>

        {detail.look.source_available && detail.source_video_ref ? (
          <button
            className="source-link"
            type="button"
            onClick={() =>
              onReturnToSource(
                detail.source_video_ref!,
                detail.source_timestamp_ms ?? 0
              )
            }
          >
            回看原视频 · {Math.round((detail.source_timestamp_ms ?? 0) / 100) / 10}s
          </button>
        ) : detail.source_video_ref ? (
          <p className="source-unavailable" role="status">
            原始画面已删除，穿搭关系和已拆出的单品仍保留。
          </p>
        ) : null}

        {detail.components.length > 0 ? (
          <section className="look-detail__section" aria-labelledby="look-components-title">
            <div className="section-heading">
              <h3 id="look-components-title">这套里的单品</h3>
              <span>{detail.components.length} 件</span>
            </div>
            <div className="look-component-strip">
              {detail.components.map((component) => (
                <article key={component.component_key}>
                  {component.item_image_url ? (
                    <img src={component.item_image_url} alt={component.role ?? "穿搭单品"} />
                  ) : (
                    <div className="item-image-placeholder">
                      <span>衣</span>
                    </div>
                  )}
                  <strong>{component.role ?? component.layer ?? "待识别单品"}</strong>
                  <small>
                    {component.item_id ? "已进入单品衣橱" : "保留中，等待补全"}
                  </small>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {detail.components.some((component) => component.item_id !== null) ? (
          <section className="look-detail__section render-studio" aria-labelledby="look-renders-title">
            <div className="section-heading">
              <h3 id="look-renders-title">穿搭成片</h3>
              <span>真实资产生成</span>
            </div>
            <div className="render-studio__tabs" role="tablist" aria-label="穿搭成片类型">
              {(
                [
                  ["collage", "真实拼贴"],
                  ["try_on", "固定模特"],
                  ["pixel_cover", "像素封面"]
                ] as const
              ).map(([kind, label]) => (
                <button
                  key={kind}
                  type="button"
                  role="tab"
                  aria-selected={activeRenderKind === kind}
                  className={activeRenderKind === kind ? "is-selected" : ""}
                  onClick={() => setActiveRenderKind(kind)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="render-studio__preview">
              {visibleRender?.output_image_url ? (
                <img
                  src={`${visibleRender.output_image_url}?v=${encodeURIComponent(
                    visibleRender.updated_at
                  )}`}
                  alt={visibleRender.presentation_label}
                  data-pixel={visibleRender.kind === "pixel_cover" ? "true" : "false"}
                />
              ) : (
                <div className="render-studio__empty">
                  <span aria-hidden="true">✦</span>
                  <strong>
                    {rendersLoading || activeRender?.status === "queued" || activeRender?.status === "running"
                      ? "正在生成穿搭成片"
                      : activeRenderKind === "collage"
                        ? "正在准备真实单品拼贴"
                        : "选择生成后，不用停在这里等"}
                  </strong>
                  <small>任务会在后台完成，退出详情也不会丢失。</small>
                </div>
              )}
              {activeRender && activeRender.status !== "succeeded" ? (
                <div className={`render-studio__status render-studio__status--${activeRender.status}`}>
                  <strong>{activeRender.presentation_label}</strong>
                  <span>
                    {activeRender.status === "queued" || activeRender.status === "running"
                      ? "后台生成中…"
                      : activeRender.failure_message ?? "已保留真实拼贴结果"}
                  </span>
                </div>
              ) : null}
            </div>
            <p className="render-studio__truth">
              {activeRenderKind === "try_on"
                ? "当前使用固定模特，不会冒充你的真人试穿。"
                : activeRenderKind === "pixel_cover"
                  ? "像素图只作为衣橱封面和分享锚点，真实单品仍以原图为准。"
                  : "拼贴直接来自这套穿搭里已入库的真实单品图。"}
            </p>
            {activeRenderKind !== "collage" && onGenerate ? (
              <button
                className="primary-action"
                type="button"
                disabled={generatingKind !== null}
                onClick={() => onGenerate(detail.look.id, activeRenderKind)}
              >
                {generatingKind === activeRenderKind
                  ? "任务启动中…"
                  : activeRenderKind === "try_on"
                    ? "生成固定模特效果"
                    : "生成像素封面"}
              </button>
            ) : null}
            {activeRenderKind === "pixel_cover" &&
            pixelCover?.share_eligible &&
            pixelCover.output_image_url ? (
              <button
                className="secondary-action"
                type="button"
                disabled={sharing}
                onClick={() => void sharePixelCover()}
              >
                {sharing ? "正在准备分享…" : "分享像素封面"}
              </button>
            ) : null}
            {shareMessage ? <p className="render-studio__message" role="status">{shareMessage}</p> : null}
          </section>
        ) : null}

        {detail.analysis ? (
          <section className="look-detail__section" aria-labelledby="look-analysis-title">
            <div className="section-heading">
              <h3 id="look-analysis-title">搭配关系</h3>
              <span>AI 理解</span>
            </div>
            <div className="look-analysis">
              {Object.entries(values).map(([key, value]) => (
                <p key={key}>
                  <span>{key}</span>
                  <strong>{value}</strong>
                </p>
              ))}
            </div>
          </section>
        ) : null}

        {detail.look.status === "partial" || detail.look.status === "error" ? (
          <div className="look-recovery" role="alert">
            <strong>
              {detail.look.status === "partial"
                ? "部分单品还没拆完整"
                : "这次还没解析成功"}
            </strong>
            <span>原始穿搭和已有结果都已保留，可以直接继续。</span>
            <button
              type="button"
              disabled={retrying || !detail.look.source_available}
              onClick={() => onRetry(detail.look.id)}
            >
              {retrying ? "正在重试…" : "重新解析"}
            </button>
          </div>
        ) : null}

        {detail.preferences.map((preference) => {
          const savedReason = preference.payload.reason;
          return typeof savedReason === "string" ? (
            <blockquote key={preference.id}>“{savedReason}”</blockquote>
          ) : null;
        })}

        <label className="form-field look-reason">
          <span>为什么喜欢这套？（可选）</span>
          <textarea
            value={reason}
            maxLength={500}
            rows={2}
            placeholder="例如：喜欢这种松弛、有层次的感觉"
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <button
          className="primary-action"
          type="button"
          disabled={saving || !reason.trim()}
          onClick={() => onSaveReason(detail.look.id, reason.trim())}
        >
          {saving ? "保存中…" : "补充喜欢原因"}
        </button>
      </div>
    </motion.section>
  );
}

export function LookDetail(props: LookDetailProps) {
  return (
    <AnimatePresence>
      {props.loading ? (
        <div className="detail-layer">
          <div className="detail-sheet look-detail__loading" aria-label="正在打开穿搭">
            正在打开穿搭…
          </div>
        </div>
      ) : props.detail ? (
        <div className="detail-layer">
          <DetailContent
            detail={props.detail}
            renders={props.renders}
            rendersLoading={props.rendersLoading}
            generatingKind={props.generatingKind}
            retrying={props.retrying}
            saving={props.saving}
            onClose={props.onClose}
            onReturnToSource={props.onReturnToSource}
            onRetry={props.onRetry}
            onSaveReason={props.onSaveReason}
            onGenerate={props.onGenerate}
          />
        </div>
      ) : null}
    </AnimatePresence>
  );
}
