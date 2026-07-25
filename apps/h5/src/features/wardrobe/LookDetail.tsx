import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import type {
  LookDetail as LookDetailData,
  PurchaseDemand,
  RenderArtifact,
  RenderKind
} from "../../api/client";
import { garmentImageAlt, garmentLabel, LOOK_ANALYSIS_LABELS } from "./localization";

type LookDetailProps = {
  detail: LookDetailData | null;
  loading: boolean;
  renders?: RenderArtifact[];
  rendersLoading?: boolean;
  purchaseDemands?: PurchaseDemand[];
  purchaseDemandsLoading?: boolean;
  updatingPurchaseDemandId?: string | null;
  generatingKind?: RenderKind | null;
  tryOnUploading?: boolean;
  deletingTryOnPhoto?: boolean;
  retrying: boolean;
  saving: boolean;
  onClose: () => void;
  onReturnToSource: (videoRef: string, timestampMs: number) => void;
  onRetry: (lookId: string) => void;
  onSaveReason: (lookId: string, reason: string) => void;
  onGenerate?: (lookId: string, kind: RenderKind) => void;
  onTryOn?: (lookId: string, file: File) => void;
  onDeleteTryOnPhoto?: (artifactId: string) => void;
  onAdvancePurchaseDemand?: (
    demandId: string,
    status: PurchaseDemand["status"]
  ) => void;
};

function DetailContent({
  detail,
  renders = [],
  rendersLoading = false,
  purchaseDemands = [],
  purchaseDemandsLoading = false,
  updatingPurchaseDemandId = null,
  generatingKind = null,
  tryOnUploading = false,
  deletingTryOnPhoto = false,
  retrying,
  saving,
  onClose,
  onReturnToSource,
  onRetry,
  onSaveReason,
  onGenerate,
  onTryOn,
  onDeleteTryOnPhoto,
  onAdvancePurchaseDemand
}: Omit<LookDetailProps, "detail" | "loading"> & {
  detail: LookDetailData;
}) {
  const [reason, setReason] = useState("");
  const [activeRenderKind, setActiveRenderKind] =
    useState<RenderKind>("collage");
  const [sharing, setSharing] = useState(false);
  const [shareMessage, setShareMessage] = useState<string | null>(null);
  const [pendingTryOnFile, setPendingTryOnFile] = useState<File | null>(null);
  const [pendingTryOnPreview, setPendingTryOnPreview] = useState<string | null>(
    null
  );
  const tryOnInputRef = useRef<HTMLInputElement>(null);
  const values = detail.analysis?.values ?? {};
  const analysisSourceLabel =
    detail.analysis?.capability_alias === "curated_seed" ||
    detail.analysis?.model_version === "human_reviewed"
      ? "人工整理 · 示例搭配解析"
      : "AI 理解";
  const heroImageUrl =
    detail.look.source_image_url ?? detail.look.display_image_url;

  useEffect(() => {
    setReason("");
    setActiveRenderKind("collage");
    setShareMessage(null);
    setPendingTryOnFile(null);
  }, [detail.look.id]);

  useEffect(() => {
    if (!pendingTryOnFile) {
      setPendingTryOnPreview(null);
      return;
    }
    const preview = URL.createObjectURL(pendingTryOnFile);
    setPendingTryOnPreview(preview);
    return () => URL.revokeObjectURL(preview);
  }, [pendingTryOnFile]);

  useEffect(() => {
    if (generatingKind) setActiveRenderKind(generatingKind);
  }, [generatingKind]);

  const sortedRenders = [...renders].sort((left, right) =>
    right.updated_at.localeCompare(left.updated_at)
  );
  const latestByKind = new Map<RenderKind, RenderArtifact>();
  const completedByKind = new Map<RenderKind, RenderArtifact>();
  sortedRenders.forEach((render) => {
    if (!latestByKind.has(render.kind)) latestByKind.set(render.kind, render);
    if (
      !completedByKind.has(render.kind) &&
      (render.status === "succeeded" || render.status === "degraded") &&
      render.output_image_url
    ) {
      completedByKind.set(render.kind, render);
    }
  });
  const activeRender = latestByKind.get(activeRenderKind);
  const completedActiveRender = completedByKind.get(activeRenderKind);
  const explicitFallback = activeRender?.fallback_artifact_id
    ? renders.find(
        (render) => render.id === activeRender.fallback_artifact_id
      )
    : undefined;
  const visibleRender =
    activeRender?.output_image_url
      ? activeRender
      : completedActiveRender ??
        (explicitFallback?.output_image_url ? explicitFallback : undefined);
  const pixelCover = completedByKind.get("pixel_cover");
  const sourceLabel =
    detail.look.source === "ai_generated"
      ? "AI 搭配保存"
      : detail.look.source === "feed_saved"
        ? detail.look.source_available
          ? "真实 Feed 来源"
          : "Feed 来源画面已删除"
        : "用户创建";

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
            alt={
              detail.look.source === "ai_generated"
                ? "AI 搭配中的真实衣橱单品"
                : "收藏的真实整套穿搭"
            }
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
          <span>{sourceLabel}</span>
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
                    <img
                      src={component.item_image_url}
                      alt={garmentImageAlt(component.role ?? component.layer)}
                    />
                  ) : (
                    <div className="item-image-placeholder">
                      <span>衣</span>
                    </div>
                  )}
                  <strong>
                    {garmentLabel(component.role ?? component.layer, "待识别单品")}
                  </strong>
                  <small>
                    {component.item_id ? "已进入单品衣橱" : "保留中，等待补全"}
                  </small>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {purchaseDemandsLoading || purchaseDemands.length > 0 ? (
          <section className="look-detail__section" aria-labelledby="purchase-list-title">
            <div className="section-heading">
              <h3 id="purchase-list-title">补齐这套</h3>
              <span>真实搜索需求</span>
            </div>
            {purchaseDemandsLoading ? (
              <p className="privacy-note">正在加载缺少的单品…</p>
            ) : (
              <div className="purchase-demand-list">
                {purchaseDemands.map((demand) => (
                  <article key={demand.id}>
                    <div>
                      <strong>{garmentLabel(demand.role)}</strong>
                      <small>
                        {demand.status === "wanted"
                          ? "待购买"
                          : demand.status === "purchased_pending"
                            ? demand.can_mark_owned
                              ? "已下单，收到后可转为我的衣服"
                              : "已下单，收到后需拍照入库"
                            : "已收到，关联单品已转为我的衣服"}
                      </small>
                    </div>
                    <a href={demand.search_url} target="_blank" rel="noreferrer">
                      去抖音搜索
                    </a>
                    {demand.status === "wanted" && onAdvancePurchaseDemand ? (
                      <button
                        type="button"
                        disabled={updatingPurchaseDemandId === demand.id}
                        onClick={() =>
                          onAdvancePurchaseDemand(demand.id, "purchased_pending")
                        }
                      >
                        {updatingPurchaseDemandId === demand.id ? "更新中…" : "标记已下单"}
                      </button>
                    ) : demand.status === "purchased_pending" &&
                      demand.can_mark_owned &&
                      onAdvancePurchaseDemand ? (
                      <button
                        type="button"
                        disabled={updatingPurchaseDemandId === demand.id}
                        onClick={() => onAdvancePurchaseDemand(demand.id, "owned")}
                      >
                        {updatingPurchaseDemandId === demand.id ? "更新中…" : "确认已收到"}
                      </button>
                    ) : demand.status === "purchased_pending" &&
                      !demand.can_mark_owned ? (
                      <span className="privacy-note">
                        收到后请拍照上传；完成识别入库后才会成为“我的衣服”。
                      </span>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
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
                  ["try_on", "真人试穿"],
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
                  data-pixel={
                    visibleRender.kind === "pixel_cover" &&
                    visibleRender.status === "succeeded"
                      ? "true"
                      : "false"
                  }
                />
              ) : (
                <div className="render-studio__empty">
                  <span aria-hidden="true">✦</span>
                  <strong>
                    {rendersLoading || activeRender?.status === "queued" || activeRender?.status === "running"
                      ? activeRenderKind === "try_on"
                        ? "正在生成真人试穿"
                        : activeRenderKind === "pixel_cover"
                          ? "正在生成像素封面"
                          : "正在准备真实单品拼贴"
                      : activeRenderKind === "collage"
                        ? "正在准备真实单品拼贴"
                        : activeRenderKind === "try_on"
                          ? "上传全身照后生成真人试穿"
                          : "生成一张像素穿搭封面"}
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
                ? activeRender?.personalized &&
                  activeRender.status === "succeeded"
                  ? "这张效果图基于你刚刚上传的全身照和本套真实单品生成，仅自己可见。"
                  : activeRender?.subject_attached &&
                      activeRender.status === "degraded"
                    ? "本次真人试穿暂时不可用，当前展示真实单品拼贴；可换张全身照重试。"
                  : "上传或拍摄一张正面全身照，AI 会把这套已保存穿搭换到你身上。"
                : activeRenderKind === "pixel_cover"
                  ? "像素图只作为衣橱封面和分享锚点，真实单品仍以原图为准。"
                  : "拼贴直接来自这套穿搭里已入库的真实单品图。"}
            </p>
            {activeRenderKind === "try_on" && onTryOn ? (
              <>
                <input
                  ref={tryOnInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
                  capture="environment"
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) setPendingTryOnFile(file);
                    event.currentTarget.value = "";
                  }}
                />
                {pendingTryOnFile && pendingTryOnPreview ? (
                  <div className="render-studio__photo-confirm">
                    <img
                      src={pendingTryOnPreview}
                      alt="待确认的试穿全身照"
                    />
                    <p>
                      确认使用这张全身照生成本套试穿。原照仅用于本次私人生成，
                      结果完成后可随时删除原照。
                    </p>
                    <div>
                      <button
                        className="secondary-action"
                        type="button"
                        onClick={() => setPendingTryOnFile(null)}
                      >
                        重选
                      </button>
                      <button
                        className="primary-action"
                        type="button"
                        onClick={() => {
                          onTryOn(detail.look.id, pendingTryOnFile);
                          setPendingTryOnFile(null);
                        }}
                      >
                        确认生成
                      </button>
                    </div>
                  </div>
                ) : null}
                <button
                  className="primary-action"
                  type="button"
                  disabled={tryOnUploading || generatingKind !== null}
                  onClick={() => tryOnInputRef.current?.click()}
                >
                  {tryOnUploading || generatingKind === "try_on"
                    ? "照片上传并生成中…"
                    : activeRender?.subject_attached
                      ? "换一张全身照"
                      : "拍照或上传全身照"}
                </button>
                {activeRender?.subject_attached && onDeleteTryOnPhoto ? (
                  <button
                    className="secondary-action"
                    type="button"
                    disabled={deletingTryOnPhoto}
                    onClick={() => onDeleteTryOnPhoto(activeRender.id)}
                  >
                    {deletingTryOnPhoto
                      ? "正在删除原照…"
                      : "删除本次全身原照"}
                  </button>
                ) : null}
              </>
            ) : null}
            {activeRenderKind === "pixel_cover" &&
            onGenerate &&
            (!activeRender ||
              activeRender.status === "failed" ||
              activeRender.status === "degraded") ? (
              <button
                className="primary-action"
                type="button"
                disabled={generatingKind !== null}
                onClick={() => onGenerate(detail.look.id, "pixel_cover")}
              >
                {generatingKind === "pixel_cover"
                  ? "任务启动中…"
                  : activeRender?.status === "degraded" ||
                      activeRender?.status === "failed"
                    ? "重新生成像素封面"
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
              <span>{analysisSourceLabel}</span>
            </div>
            <div className="look-analysis">
              {Object.entries(values).map(([key, value]) => (
                <p key={key}>
                  <span>{LOOK_ANALYSIS_LABELS[key] ?? key}</span>
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
            purchaseDemands={props.purchaseDemands}
            purchaseDemandsLoading={props.purchaseDemandsLoading}
            updatingPurchaseDemandId={props.updatingPurchaseDemandId}
            generatingKind={props.generatingKind}
            tryOnUploading={props.tryOnUploading}
            deletingTryOnPhoto={props.deletingTryOnPhoto}
            retrying={props.retrying}
            saving={props.saving}
            onClose={props.onClose}
            onReturnToSource={props.onReturnToSource}
            onRetry={props.onRetry}
            onSaveReason={props.onSaveReason}
            onGenerate={props.onGenerate}
            onTryOn={props.onTryOn}
            onDeleteTryOnPhoto={props.onDeleteTryOnPhoto}
            onAdvancePurchaseDemand={props.onAdvancePurchaseDemand}
          />
        </div>
      ) : null}
    </AnimatePresence>
  );
}
