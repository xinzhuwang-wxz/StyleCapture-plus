import { AnimatePresence, motion } from "motion/react";

import { useEffect, useRef, useState } from "react";

import {
  validateImage,
  type LookDetail as LookDetailData,
  type PurchaseDemand,
  type RenderArtifact,
  type RenderKind
} from "../../api/client";
import { ShareCardSheet } from "../outfit/ShareCardSheet";
import {
  createBrowserImagePreview,
  releaseBrowserImagePreview
} from "../../media/browserImagePreview";
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
  deletingSource?: boolean;
  retrying: boolean;
  saving: boolean;
  onClose: () => void;
  onReturnToSource: (videoRef: string, timestampMs: number) => void;
  onRetry: (lookId: string) => void;
  onSaveReason: (lookId: string, reason: string) => void;
  onGenerate?: (lookId: string, kind: RenderKind) => void;
  onTryOn?: (lookId: string, file: File) => void;
  onDeleteTryOnPhoto?: (artifactId: string) => void;
  onDeleteSource?: (lookId: string) => void;
  onAdvancePurchaseDemand?: (
    demandId: string,
    status: PurchaseDemand["status"]
  ) => void;
  /** 打开衣橱里已有的那件单品。没有这个回调时单品条保持不可点。 */
  onOpenItem?: (itemId: string) => void;
};

const RENDER_STUDIO_KINDS = ["try_on", "pixel_cover"] as const;
type RenderStudioKind = (typeof RENDER_STUDIO_KINDS)[number];

function isRenderStudioKind(kind: RenderKind | null): kind is RenderStudioKind {
  return kind === "try_on" || kind === "pixel_cover";
}

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
  deletingSource = false,
  retrying,
  saving,
  onOpenItem,
  onClose,
  onReturnToSource,
  onRetry,
  onSaveReason,
  onGenerate,
  onTryOn,
  onDeleteTryOnPhoto,
  onDeleteSource,
  onAdvancePurchaseDemand
}: Omit<LookDetailProps, "detail" | "loading"> & {
  detail: LookDetailData;
}) {
  const [reason, setReason] = useState("");
  const [activeRenderKind, setActiveRenderKind] =
    useState<RenderStudioKind>("try_on");
  const [sharing, setSharing] = useState(false);
  const [shareMessage, setShareMessage] = useState<string | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const [pendingTryOnFile, setPendingTryOnFile] = useState<File | null>(null);
  const [pendingTryOnPreview, setPendingTryOnPreview] = useState<string | null>(
    null
  );
  const [tryOnValidationError, setTryOnValidationError] = useState<string | null>(null);
  const [confirmingSourceDelete, setConfirmingSourceDelete] = useState(false);
  const tryOnInputRef = useRef<HTMLInputElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  const values = detail.analysis?.values ?? {};
  const analysisSourceLabel =
    detail.analysis?.capability_alias === "curated_seed" ||
    detail.analysis?.model_version === "human_reviewed"
      ? "人工整理 · 示例搭配解析"
      : "AI 理解";
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
  const usableCollage = sortedRenders.find(
    (render) =>
      render.kind === "collage" &&
      (render.status === "succeeded" || render.status === "degraded") &&
      render.output_image_url
  );
  const latestCollage = latestByKind.get("collage");
  const usesFixedCuratedPresentation = detail.look.fixed_presentation === true;
  const showCollagePlaceholder =
    !usesFixedCuratedPresentation &&
    !usableCollage &&
    (latestCollage?.status === "queued" ||
      latestCollage?.status === "running");
  const collageNeedsRetry =
    !usesFixedCuratedPresentation &&
    latestCollage !== undefined &&
    (latestCollage.status === "failed" ||
      ((latestCollage.status === "succeeded" ||
        latestCollage.status === "degraded") &&
        !latestCollage.output_image_url));
  const heroImageUrl =
    usesFixedCuratedPresentation
      ? detail.look.display_image_url ?? detail.look.source_image_url
      : usableCollage?.output_image_url ??
        detail.look.display_image_url ??
        detail.look.source_image_url;

  useEffect(() => {
    setReason("");
    setActiveRenderKind(
      latestByKind.has("try_on")
        ? "try_on"
        : latestByKind.has("pixel_cover")
          ? "pixel_cover"
          : "try_on"
    );
    setShareMessage(null);
    setPendingTryOnFile(null);
    setTryOnValidationError(null);
    setConfirmingSourceDelete(false);
  }, [detail.look.id]);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previouslyFocused = document.activeElement;
    closeButtonRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      onCloseRef.current();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      if (previouslyFocused instanceof HTMLElement && previouslyFocused.isConnected) {
        previouslyFocused.focus();
      }
    };
  }, [detail.look.id]);

  useEffect(() => {
    if (!pendingTryOnFile) {
      setPendingTryOnPreview(null);
      return;
    }
    const preview = createBrowserImagePreview(pendingTryOnFile);
    setPendingTryOnPreview(preview);
    return () => releaseBrowserImagePreview(preview);
  }, [pendingTryOnFile]);

  useEffect(() => {
    if (isRenderStudioKind(generatingKind)) setActiveRenderKind(generatingKind);
  }, [generatingKind]);

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
  const lookStatusLabel =
    detail.look.status === "ready"
      ? "搭配分析完成"
      : detail.look.status === "error"
        ? "解析失败，结果已保留"
        : detail.look.status === "partial"
          ? "部分拆解完成"
          : "后台处理中";

  /** 只下载，不走系统面板——「保存到相册」要的就是这条。 */
  async function downloadPixelCover() {
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
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `stylecapture-${detail.look.id}.png`;
      link.click();
      URL.revokeObjectURL(url);
      setShareMessage("像素封面已保存");
    } catch (error) {
      setShareMessage(error instanceof Error ? error.message : "保存没有完成");
    } finally {
      setSharing(false);
    }
  }

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
        <button
          ref={closeButtonRef}
          className="icon-button"
          type="button"
          aria-label="返回衣橱"
          onClick={onClose}
        >
          ‹
        </button>
        <strong id="look-detail-title">穿搭详情</strong>
        <span className="detail-topbar__spacer" />
      </div>

      <div className="detail-image look-detail__hero">
        {showCollagePlaceholder ? (
          <div className="look-detail__collage-placeholder" role="img" aria-label="真实单品拼贴生成中">
            <span aria-hidden="true">✦</span>
            <strong>
              {latestCollage?.status === "queued"
                ? "真实单品拼贴排队中"
                : "正在生成真实单品拼贴"}
            </strong>
            <small>完成后会优先作为这套穿搭的详情封面。</small>
          </div>
        ) : heroImageUrl ? (
          <img
            src={
              usableCollage && !usesFixedCuratedPresentation
                ? `${heroImageUrl}?v=${encodeURIComponent(usableCollage.updated_at)}`
                : heroImageUrl
            }
            alt={
              usableCollage && !usesFixedCuratedPresentation
                ? usableCollage.presentation_label
                : detail.look.source === "ai_generated"
                ? "AI 搭配中的真实衣橱单品"
                : "收藏的真实整套穿搭"
            }
          />
        ) : (
          <div className="item-image-placeholder">
            <span>✦</span>
            <small>
              {detail.look.source === "ai_generated"
                ? "由衣橱真实单品组成"
                : "原始画面已删除"}
            </small>
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
          <span>{lookStatusLabel}</span>
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

        {detail.look.source !== "ai_generated" &&
        detail.look.source_available &&
        onDeleteSource ? (
          confirmingSourceDelete ? (
            <div className="look-recovery" role="alertdialog" aria-label="确认删除整套原图">
              <strong>删除整套原图？</strong>
              <span>
                已拆出的单品、搭配关系和生成结果都会保留；删除后不能重新解析原图。
              </span>
              <div className="look-detail__source-actions">
                <button
                  className="secondary-action"
                  type="button"
                  disabled={deletingSource}
                  onClick={() => setConfirmingSourceDelete(false)}
                >
                  取消
                </button>
                <button
                  className="secondary-action"
                  type="button"
                  disabled={deletingSource}
                  onClick={() => onDeleteSource(detail.look.id)}
                >
                  {deletingSource ? "正在删除…" : "确认删除原图"}
                </button>
              </div>
            </div>
          ) : (
            <button
              className="source-link"
              type="button"
              onClick={() => setConfirmingSourceDelete(true)}
            >
              删除整套原图
            </button>
          )
        ) : null}

        {collageNeedsRetry && onGenerate ? (
          <div className="look-recovery" role="status">
            <strong>真实单品拼贴暂未生成</strong>
            <span>原始穿搭和已拆单品都已保留，可以重新生成。</span>
            <button
              className="secondary-action"
              type="button"
              disabled={generatingKind !== null}
              onClick={() => onGenerate(detail.look.id, "collage")}
            >
              {generatingKind === "collage" ? "正在重新生成…" : "重新生成真实拼贴"}
            </button>
          </div>
        ) : null}

        {detail.components.length > 0 ? (
          <section className="look-detail__section" aria-labelledby="look-components-title">
            <div className="section-heading">
              <h3 id="look-components-title">套装所含单品</h3>
              <span>{detail.components.length} 件</span>
            </div>
            <div className="look-component-strip">
              {detail.components.map((component) => {
                const label = garmentLabel(
                  component.role ?? component.layer,
                  "待识别单品"
                );
                // 衣橱里没有这件时，用后端为这个位置算好的采购需求去搜同款。
                // 只在真有搜索词时才给这条出口——拿角色名（「上装」）去搜是
                // 搜不到东西的，给一个点了没用的按钮比不给更糟。
                const demand = component.item_id
                  ? undefined
                  : purchaseDemands.find(
                      (candidate) => candidate.role === component.role
                    );
                const canOpen = Boolean(component.item_id && onOpenItem);
                const canShop = Boolean(demand?.search_url);
                const body = (
                  <>
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
                    <strong>{label}</strong>
                    <small>
                      {component.item_id
                        ? "已进入单品衣橱"
                        : canShop
                          ? "衣橱里没有 · 去抖音看同款 ›"
                          : "保留中，等待补全"}
                    </small>
                  </>
                );

                if (canOpen) {
                  return (
                    <button
                      key={component.component_key}
                      type="button"
                      className="look-component-strip__link"
                      aria-label={`打开单品：${label}`}
                      onClick={() => onOpenItem?.(component.item_id as string)}
                    >
                      {body}
                    </button>
                  );
                }
                if (canShop) {
                  return (
                    <a
                      key={component.component_key}
                      className="look-component-strip__link look-component-strip__link--shop"
                      href={demand!.search_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      aria-label={`去抖音搜索同款：${demand!.search_query}`}
                    >
                      {body}
                    </a>
                  );
                }
                return (
                  <article key={component.component_key}>{body}</article>
                );
              })}
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
                              ? "已下单，收到后可转为已拥有"
                              : "已下单，收到后需拍照入库"
                            : "已收到，关联单品已转为已拥有"}
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
                        收到后请拍照上传；完成识别入库后才会成为「已拥有」。
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
                RENDER_STUDIO_KINDS.map((kind) => [
                  kind,
                  kind === "try_on" ? "真人试穿" : "像素封面"
                ] as const)
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
            <div className="render-studio__preview" data-render-kind={activeRenderKind}>
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
                        : "正在生成像素封面"
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
                      : activeRender.kind === "try_on"
                        ? "真人试穿暂时不可用，已保留真实单品拼贴；可换张全身照重试。"
                        : activeRender.kind === "pixel_cover"
                          ? "像素封面暂时不可用，真实单品和穿搭关系不受影响。"
                          : "真实单品拼贴暂时不可用，请稍后重试。"}
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
                : "像素图只作为衣橱封面和分享锚点，真实单品仍以原图为准。"}
            </p>
            {activeRenderKind === "try_on" && onTryOn ? (
              <>
                <input
                  ref={tryOnInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
                  capture="user"
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      const validationError = validateImage(file);
                      if (validationError) {
                        setPendingTryOnFile(null);
                        setTryOnValidationError(validationError);
                      } else {
                        setTryOnValidationError(null);
                        setPendingTryOnFile(file);
                      }
                    }
                    event.currentTarget.value = "";
                  }}
                />
                {tryOnValidationError ? (
                  <div className="profile__error" role="alert">
                    {tryOnValidationError}
                  </div>
                ) : null}
                {pendingTryOnFile ? (
                  <div className="render-studio__photo-confirm">
                    {pendingTryOnPreview ? (
                      <img
                        src={pendingTryOnPreview}
                        alt="待确认的试穿全身照"
                      />
                    ) : (
                      <div className="pending-heic-preview" role="status">
                        <strong>iPhone 全身照已选中</strong>
                        <span>确认后会自动转换并用于私人试穿</span>
                      </div>
                    )}
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
                onClick={() => setShareOpen(true)}
              >
                {sharing ? "正在准备分享…" : "分享像素封面"}
              </button>
            ) : null}
            {shareMessage ? <p className="render-studio__message" role="status">{shareMessage}</p> : null}
            {shareOpen && pixelCover?.output_image_url ? (
              <ShareCardSheet
                imageUrl={pixelCover.output_image_url}
                title="我的穿搭"
                sharing={sharing}
                message={shareMessage}
                onShare={sharePixelCover}
                onSave={downloadPixelCover}
                onClose={() => setShareOpen(false)}
              />
            ) : null}
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
            deletingSource={props.deletingSource}
            retrying={props.retrying}
            saving={props.saving}
            onOpenItem={props.onOpenItem}
            onClose={props.onClose}
            onReturnToSource={props.onReturnToSource}
            onRetry={props.onRetry}
            onSaveReason={props.onSaveReason}
            onGenerate={props.onGenerate}
            onTryOn={props.onTryOn}
            onDeleteTryOnPhoto={props.onDeleteTryOnPhoto}
            onDeleteSource={props.onDeleteSource}
            onAdvancePurchaseDemand={props.onAdvancePurchaseDemand}
          />
        </div>
      ) : null}
    </AnimatePresence>
  );
}
