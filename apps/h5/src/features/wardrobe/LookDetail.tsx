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
import type { LookItemAction } from "./LookItemActionSheet";
import { DeleteAssetDialog, type LookDeleteScope } from "./DeleteAssetDialog";

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
  deletingLook?: boolean;
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
  onDeleteLook?: (lookId: string, scope: LookDeleteScope) => void;
  onAdvancePurchaseDemand?: (
    demandId: string,
    status: PurchaseDemand["status"]
  ) => void;
  /** 根据后端归属显示这件单品的下一步操作。 */
  onOpenItem?: (action: LookItemAction) => void;
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
  deletingLook = false,
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
  onDeleteLook,
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
  const [deletingLookOpen, setDeletingLookOpen] = useState(false);
  const [heroTryOnRevealed, setHeroTryOnRevealed] = useState(false);
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
      render.current !== false &&
      (render.status === "succeeded" || render.status === "degraded") &&
      render.output_image_url
  );
  const latestCollage = latestByKind.get("collage");
  const usesFixedCuratedPresentation = detail.look.fixed_presentation === true;
  const trackedComponentPresentations = detail.components.filter(
    (component) => component.item_image_status
  );
  const readyComponentPresentationCount = trackedComponentPresentations.filter(
    (component) => component.item_image_status === "succeeded"
  ).length;
  const componentImagesGenerating = trackedComponentPresentations.some(
    (component) =>
      component.item_image_status === "queued" ||
      component.item_image_status === "running"
  );
  const collageRenderGenerating =
    latestCollage?.status === "queued" || latestCollage?.status === "running";
  const showCollagePlaceholder =
    !usesFixedCuratedPresentation &&
    !usableCollage &&
    (componentImagesGenerating ||
      detail.look.status === "processing" ||
      collageRenderGenerating);
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
  const pendingHeroImageUrl =
    detail.look.source_image_url ?? detail.look.display_image_url;
  const completedTryOn = completedByKind.get("try_on");
  const tryOnPreviewUrl =
    completedTryOn?.output_image_url ??
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
    setDeletingLookOpen(false);
    setHeroTryOnRevealed(false);
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
      if (deletingLookOpen) setDeletingLookOpen(false);
      else onCloseRef.current();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      if (previouslyFocused instanceof HTMLElement && previouslyFocused.isConnected) {
        previouslyFocused.focus();
      }
    };
  }, [deletingLookOpen, detail.look.id]);

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
        {onDeleteLook ? (
          <button
            className="icon-button detail-delete-button"
            type="button"
            aria-label="删除穿搭"
            onClick={() => setDeletingLookOpen(true)}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5" />
            </svg>
          </button>
        ) : (
          <span className="detail-topbar__spacer" />
        )}
      </div>

      <div className="detail-image look-detail__hero">
        <div
          className="look-detail__hero-panel look-detail__hero-flatlay"
          role={showCollagePlaceholder ? "img" : undefined}
          aria-label={showCollagePlaceholder ? "真实单品拼贴生成中" : undefined}
        >
          {usableCollage?.output_image_url && !usesFixedCuratedPresentation ? (
            <img
              src={`${usableCollage.output_image_url}?v=${encodeURIComponent(usableCollage.updated_at)}`}
              alt={usableCollage.presentation_label}
            />
          ) : detail.components.some((component) => component.item_image_url) ? (
            <div className="look-detail__flatlay-items" aria-label="套装单品平面拼贴">
              {detail.components
                .filter((component) => component.item_image_url)
                .slice(0, 4)
                .map((component) => (
                  <img
                    key={component.component_key}
                    className={
                      component.item_image_status === "queued" ||
                      component.item_image_status === "running"
                        ? "is-generating"
                        : undefined
                    }
                    src={component.item_image_url!}
                    alt={garmentImageAlt(component.role ?? component.layer)}
                  />
                ))}
            </div>
          ) : showCollagePlaceholder && pendingHeroImageUrl ? (
            <img
              className="look-detail__pending-source"
              src={pendingHeroImageUrl}
              alt="正在处理的原始穿搭"
            />
          ) : heroImageUrl ? (
            <img src={heroImageUrl} alt="收藏的真实整套穿搭" />
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

          {showCollagePlaceholder ? (
            <div
              className="look-detail__collage-status"
              role="status"
              aria-live="polite"
            >
              <span className="item-flat-lay-spinner" aria-hidden="true" />
              <div className="look-detail__collage-status-copy">
                <strong>
                  {componentImagesGenerating
                    ? `正在生成单品图 ${readyComponentPresentationCount}/${trackedComponentPresentations.length}`
                    : "正在生成整套拼贴"}
                </strong>
                <small>完成后会自动替换当前截图</small>
                {componentImagesGenerating ? (
                  <progress
                    aria-label="单品图生成进度"
                    value={readyComponentPresentationCount}
                    max={trackedComponentPresentations.length}
                  />
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="look-detail__tryon-card">
        <div className={`look-detail__tryon-thumb${heroTryOnRevealed ? " is-revealed" : ""}`}>
          {tryOnPreviewUrl ? (
            <img src={tryOnPreviewUrl} alt="真人试穿预览" />
          ) : (
            <div className="look-detail__tryon-empty" aria-hidden="true">人</div>
          )}
          <span aria-hidden="true">✦</span>
        </div>
        <div className="look-detail__tryon-copy">
          <strong>查看真人试穿效果</strong>
          <small>
            {completedTryOn?.output_image_url
              ? "点击查看清晰试穿效果"
              : "点击后生成并展示模特试穿效果"}
          </small>
        </div>
        <button
          type="button"
          onClick={() => {
            if (completedTryOn?.output_image_url) {
              setHeroTryOnRevealed((current) => !current);
            } else {
              setActiveRenderKind("try_on");
              tryOnInputRef.current?.click();
            }
          }}
        >
          <span aria-hidden="true">✦</span>
          {completedTryOn?.output_image_url
            ? heroTryOnRevealed
              ? "收起效果"
              : "查看效果"
            : "生成试穿"}
        </button>
      </div>

      <div className="detail-content">
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
        ) : detail.look.source !== "ai_generated" && detail.source_video_ref ? (
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
                const itemImageGenerating =
                  component.item_image_status === "queued" ||
                  component.item_image_status === "running";
                const itemImageFailed = component.item_image_status === "failed";
                // 衣橱里没有这件时，用后端为这个位置算好的采购需求去搜同款。
                // 只在真有搜索词时才给这条出口——拿角色名（「上装」）去搜是
                // 搜不到东西的，给一个点了没用的按钮比不给更糟。
                const demand = purchaseDemands.find((candidate) =>
                  component.item_id
                    ? candidate.item_id === component.item_id
                    : candidate.role === component.role
                );
                const canShop = Boolean(demand?.search_url);
                const canOpen = Boolean(onOpenItem && (component.item_id || canShop));
                // Look component only carries the wardrobe item id. App enriches
                // this fallback from the backend ItemResponse before opening the sheet.
                const ownership = "inspiration" as const;
                const body = (
                  <>
                    <div
                      className={`look-component-strip__media${itemImageGenerating ? " is-generating" : ""}`}
                    >
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
                      {itemImageGenerating ? (
                        <span
                          className="look-component-strip__loading"
                          role="status"
                          aria-label={`${label}白底单品图生成中`}
                        >
                          <span className="item-flat-lay-spinner" aria-hidden="true" />
                          <em>生成中</em>
                        </span>
                      ) : null}
                    </div>
                    <strong>{label}</strong>
                    <small>
                      {itemImageGenerating
                        ? "正在生成白底单品图"
                        : itemImageFailed
                          ? "暂用截图 · 稍后可重试"
                          : component.item_id
                        ? "查看单品操作"
                        : canShop
                          ? "衣橱里没有 · 去抖音看同款 ›"
                          : "保留中，等待补全"}
                    </small>
                    <span className="look-component-strip__arrow" aria-hidden="true">›</span>
                  </>
                );

                if (canOpen) {
                  return (
                    <button
                      key={component.component_key}
                      type="button"
                      className="look-component-strip__link"
                      aria-label={`查看单品操作：${label}`}
                      onClick={() =>
                        onOpenItem?.({
                          itemId: component.item_id,
                          label,
                          imageUrl: component.item_image_url,
                          ownership,
                          purchaseSearchUrl: demand?.search_url ?? null
                        })
                      }
                    >
                      {body}
                    </button>
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
      <DeleteAssetDialog
        kind="look"
        open={deletingLookOpen}
        busy={deletingLook}
        onClose={() => setDeletingLookOpen(false)}
        onConfirm={(scope) => {
          if (scope) onDeleteLook?.(detail.look.id, scope);
        }}
      />
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
            deletingLook={props.deletingLook}
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
            onDeleteLook={props.onDeleteLook}
            onAdvancePurchaseDemand={props.onAdvancePurchaseDemand}
          />
        </div>
      ) : null}
    </AnimatePresence>
  );
}
