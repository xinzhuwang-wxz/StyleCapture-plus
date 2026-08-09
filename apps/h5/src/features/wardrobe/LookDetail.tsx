import { AnimatePresence, motion } from "motion/react";

import { useEffect, useRef, useState } from "react";

import {
  type LookDetail as LookDetailData,
  type PurchaseDemand,
  type RenderArtifact,
  type RenderKind
} from "../../api/client";
import { TryOnPhotoSheet } from "../profile/TryOnPhotoSheet";
import { emptyAlbum, type PhotoAlbum } from "../profile/photoStorage";
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
  photoAlbum?: PhotoAlbum;
  onPhotoAlbumChange?: (album: PhotoAlbum) => void;
  deletingTryOnPhoto?: boolean;
  deletingSource?: boolean;
  deletingLook?: boolean;
  retrying: boolean;
  saving: boolean;
  onClose: () => void;
  onReturnToSource: (videoRef: string, timestampMs: number) => void;
  onRetry: (lookId: string) => void;
  onSaveReason: (lookId: string, reason: string) => void;
  onGenerate?: (
    lookId: string,
    kind: RenderKind,
    sourceArtifactId?: string
  ) => void;
  onSetPixelCover?: (lookId: string, artifactId: string) => void;
  activePixelCoverId?: string | null;
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

function DetailContent({
  detail,
  renders = [],
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
  onSetPixelCover,
  activePixelCoverId = null,
  onDeleteTryOnPhoto,
  onDeleteSource,
  onDeleteLook,
  onAdvancePurchaseDemand,
  tryOnPhotoPickerOpen,
  onOpenTryOnPicker,
  onCloseTryOnPicker
}: Omit<
  LookDetailProps,
  "detail" | "loading" | "photoAlbum" | "onPhotoAlbumChange"
> & {
  detail: LookDetailData;
  tryOnPhotoPickerOpen: boolean;
  onOpenTryOnPicker: () => void;
  onCloseTryOnPicker: () => void;
}) {
  const [reason, setReason] = useState("");
  const [shareMessage, setShareMessage] = useState<string | null>(null);
  const [pixelTaskOpen, setPixelTaskOpen] = useState(false);
  const [pixelTaskCollapsed, setPixelTaskCollapsed] = useState(false);
  const [pixelCoverConfirmed, setPixelCoverConfirmed] = useState(false);
  const [awaitingTryOnResult, setAwaitingTryOnResult] = useState(false);
  const [confirmingSourceDelete, setConfirmingSourceDelete] = useState(false);
  const [deletingLookOpen, setDeletingLookOpen] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const tryOnResultRef = useRef<HTMLElement>(null);
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
  sortedRenders.forEach((render) => {
    if (!latestByKind.has(render.kind)) latestByKind.set(render.kind, render);
  });
  const usesFixedCuratedPresentation = detail.look.fixed_presentation === true;
  const flatlayComponents = detail.components
    .filter((component) => component.item_image_url)
    .slice(0, 6);
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
  const showCollagePlaceholder =
    !usesFixedCuratedPresentation &&
    (componentImagesGenerating ||
      (flatlayComponents.length === 0 && detail.look.status === "processing"));
  const heroImageUrl =
    detail.look.display_image_url ?? detail.look.source_image_url;
  const pendingHeroImageUrl =
    detail.look.source_image_url ?? detail.look.display_image_url;
  const completedTryOn = sortedRenders.find(
    (render) =>
      render.kind === "try_on" &&
      render.status === "succeeded" &&
      Boolean(render.output_image_url)
  );
  const tryOnPreviewUrl =
    completedTryOn?.output_image_url ??
    detail.look.display_image_url ??
    detail.look.source_image_url;

  useEffect(() => {
    setReason("");
    setShareMessage(null);
    setPixelTaskOpen(false);
    setPixelTaskCollapsed(false);
    setPixelCoverConfirmed(false);
    setAwaitingTryOnResult(false);
    setConfirmingSourceDelete(false);
    setDeletingLookOpen(false);
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
      if (tryOnPhotoPickerOpen) onCloseTryOnPicker();
      else if (deletingLookOpen) setDeletingLookOpen(false);
      else onCloseRef.current();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      if (previouslyFocused instanceof HTMLElement && previouslyFocused.isConnected) {
        previouslyFocused.focus();
      }
    };
  }, [
    deletingLookOpen,
    detail.look.id,
    onCloseTryOnPicker,
    tryOnPhotoPickerOpen
  ]);

  const latestTryOn = latestByKind.get("try_on");
  const latestPixel = latestByKind.get("pixel_cover");
  const pixelCover = sortedRenders.find(
    (render) =>
      render.kind === "pixel_cover" &&
      render.status === "succeeded" &&
      Boolean(render.output_image_url)
  );
  const pixelTaskBusy =
    generatingKind === "pixel_cover" ||
    latestPixel?.status === "queued" ||
    latestPixel?.status === "running";
  const pixelTaskFailed =
    latestPixel?.status === "failed" || latestPixel?.status === "degraded";
  const pixelTaskReady = Boolean(pixelCover) && !pixelTaskBusy;

  useEffect(() => {
    if (tryOnUploading || generatingKind === "try_on") {
      setAwaitingTryOnResult(true);
    }
  }, [generatingKind, tryOnUploading]);

  useEffect(() => {
    if (!awaitingTryOnResult || !completedTryOn) return;
    setAwaitingTryOnResult(false);
    window.setTimeout(() => {
      tryOnResultRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
  }, [awaitingTryOnResult, completedTryOn]);

  useEffect(() => {
    if (generatingKind !== "pixel_cover") return;
    setPixelTaskOpen(true);
    setPixelTaskCollapsed(false);
  }, [generatingKind]);

  /** 只下载，不走系统面板——「保存到相册」要的就是这条。 */
  async function downloadPixelCover() {
    if (!pixelCover?.share_eligible || !pixelCover.output_image_url) return;
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
    }
  }

  async function downloadTryOnImage() {
    if (!completedTryOn?.output_image_url) return;
    setShareMessage(null);
    try {
      const response = await fetch(completedTryOn.output_image_url, {
        cache: "no-store",
        credentials: "same-origin"
      });
      if (!response.ok) throw new Error("真人试穿照片暂时无法读取");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `stylecapture-try-on-${detail.look.id}.png`;
      link.click();
      URL.revokeObjectURL(url);
      setShareMessage("真人试穿照片已保存");
    } catch (error) {
      setShareMessage(error instanceof Error ? error.message : "保存没有完成");
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
          aria-label={showCollagePlaceholder ? "单品图生成中" : undefined}
        >
          {flatlayComponents.length > 0 ? (
            <div
              className="look-detail__flatlay-items"
              data-count={flatlayComponents.length}
              aria-label="套装单品平面拼贴"
            >
              {flatlayComponents.map((component) => (
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
                    : "正在识别并整理单品"}
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
        <div className="look-detail__tryon-thumb">
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
              : "选择形象照并生成试穿效果"}
          </small>
        </div>
        <button
          type="button"
          onClick={() => {
            if (completedTryOn?.output_image_url) {
              tryOnResultRef.current?.scrollIntoView({
                behavior: "smooth",
                block: "center"
              });
            } else {
              onOpenTryOnPicker();
            }
          }}
        >
          <span aria-hidden="true">✦</span>
          查看效果
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

        {detail.components.some((component) => component.item_id !== null) &&
        (completedTryOn || latestTryOn) ? (
          <section
            ref={tryOnResultRef}
            className="look-detail__section tryon-result"
            aria-labelledby="look-tryon-result-title"
          >
            <div className="section-heading">
              <h3 id="look-tryon-result-title">真人试穿</h3>
              <span>
                {completedTryOn
                  ? "生成完成"
                  : latestTryOn?.status === "failed" || latestTryOn?.status === "degraded"
                    ? "本次未完成"
                    : "后台生成中"}
              </span>
            </div>
            {completedTryOn?.output_image_url ? (
              <div className="tryon-result__card">
                <img
                  src={`${completedTryOn.output_image_url}?v=${encodeURIComponent(
                    completedTryOn.updated_at
                  )}`}
                  alt="真人试穿穿搭卡片"
                />
                <div className="tryon-result__copy">
                  <strong>这套穿搭的真人效果</strong>
                  <small>仅自己可见，可保存或继续生成像素卡片。</small>
                </div>
                <div className="tryon-result__actions">
                  {onGenerate ? (
                    <button
                      className="primary-action"
                      type="button"
                      disabled={generatingKind !== null || pixelTaskBusy}
                      onClick={() => {
                        setPixelTaskOpen(true);
                        setPixelTaskCollapsed(false);
                        setPixelCoverConfirmed(false);
                        onGenerate(
                          detail.look.id,
                          "pixel_cover",
                          completedTryOn.id
                        );
                      }}
                    >
                      {pixelTaskBusy
                        ? "像素卡片生成中…"
                        : pixelCover
                          ? "重新生成像素卡片"
                          : "生成像素卡片"}
                    </button>
                  ) : null}
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() => void downloadTryOnImage()}
                  >
                    保存到本地照片
                  </button>
                </div>
                {latestTryOn?.subject_attached && onDeleteTryOnPhoto ? (
                  <button
                    className="tryon-result__privacy-action"
                    type="button"
                    disabled={deletingTryOnPhoto}
                    onClick={() => onDeleteTryOnPhoto(latestTryOn.id)}
                  >
                    {deletingTryOnPhoto ? "正在删除本次原照…" : "删除本次全身原照"}
                  </button>
                ) : null}
              </div>
            ) : (
              <div className="tryon-result__pending" role="status">
                <span className="item-flat-lay-spinner" aria-hidden="true" />
                <div>
                  <strong>
                    {latestTryOn?.status === "failed" || latestTryOn?.status === "degraded"
                      ? "真人试穿暂时不可用"
                      : "正在生成真人试穿"}
                  </strong>
                  <small>
                    {latestTryOn?.status === "failed" || latestTryOn?.status === "degraded"
                      ? "请回到上方“查看效果”重新选择形象照。"
                      : "任务会在后台完成，退出详情也不会丢失。"}
                  </small>
                </div>
              </div>
            )}
            {shareMessage ? (
              <p className="render-studio__message" role="status">{shareMessage}</p>
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
      {pixelTaskCollapsed && (pixelTaskBusy || pixelTaskReady || pixelTaskFailed) ? (
        <button
          className="render-task-orb"
          type="button"
          data-ready={pixelTaskReady ? "true" : undefined}
          aria-label={pixelTaskReady ? "像素卡片已生成，查看结果" : "查看像素卡片生成进度"}
          onClick={() => {
            setPixelTaskOpen(true);
            setPixelTaskCollapsed(false);
          }}
        >
          <span aria-hidden="true">✦</span>
        </button>
      ) : null}
      <AnimatePresence>
        {pixelTaskOpen ? (
          <motion.div
            className="render-task-layer"
            role="presentation"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={(event) => {
              if (event.target !== event.currentTarget) return;
              setPixelTaskOpen(false);
              setPixelTaskCollapsed(true);
            }}
          >
            <motion.section
              className="render-task-sheet"
              role="dialog"
              aria-modal="true"
              aria-labelledby="pixel-task-title"
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 320 }}
            >
              <div className="sheet-handle" aria-hidden="true" />
              <header className="render-task-sheet__header">
                <div>
                  <h2 id="pixel-task-title">
                    {pixelTaskReady
                      ? "像素卡片已生成"
                      : pixelTaskFailed
                        ? "像素卡片暂未生成"
                        : "正在生成像素卡片"}
                  </h2>
                  <p>
                    {pixelTaskReady
                      ? "这张卡片来自本次穿搭，可设为衣橱中的穿搭封面。"
                      : pixelTaskFailed
                        ? "真人试穿照片仍然保留，可以重新发起生成。"
                        : "任务会在后台继续，收起后不影响浏览。"}
                  </p>
                </div>
                <button
                  type="button"
                  aria-label={pixelTaskBusy ? "收起像素生成任务" : "关闭像素卡片结果"}
                  onClick={() => {
                    setPixelTaskOpen(false);
                    setPixelTaskCollapsed(pixelTaskBusy);
                  }}
                >
                  ×
                </button>
              </header>

              {pixelTaskReady && pixelCover?.output_image_url ? (
                <div className="render-task-sheet__preview">
                  <img
                    src={`${pixelCover.output_image_url}?v=${encodeURIComponent(
                      pixelCover.updated_at
                    )}`}
                    alt="已生成的像素穿搭卡片"
                    data-pixel="true"
                  />
                </div>
              ) : (
                <div className="render-task-sheet__pending" role="status">
                  <span className="item-flat-lay-spinner" aria-hidden="true" />
                  <strong>
                    {pixelTaskFailed ? "这次没有生成成功" : "正在后台生成，请稍后"}
                  </strong>
                </div>
              )}

              {pixelTaskReady && pixelCover ? (
                <div className="render-task-sheet__actions">
                  <button
                    className="primary-action"
                    type="button"
                    disabled={pixelCoverConfirmed || activePixelCoverId === pixelCover.id}
                    onClick={() => {
                      onSetPixelCover?.(detail.look.id, pixelCover.id);
                      setPixelCoverConfirmed(true);
                    }}
                  >
                    {pixelCoverConfirmed || activePixelCoverId === pixelCover.id
                      ? "已设为像素封面"
                      : "设为像素封面"}
                  </button>
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() => void downloadPixelCover()}
                  >
                    保存到相册
                  </button>
                  <button
                    className="render-task-sheet__dismiss"
                    type="button"
                    onClick={() => {
                      setPixelTaskOpen(false);
                      setPixelTaskCollapsed(false);
                    }}
                  >
                    暂不保存
                  </button>
                </div>
              ) : pixelTaskFailed && onGenerate ? (
                <button
                  className="primary-action"
                  type="button"
                  disabled={generatingKind !== null}
                  onClick={() => {
                    setPixelCoverConfirmed(false);
                    onGenerate(
                      detail.look.id,
                      "pixel_cover",
                      completedTryOn?.id
                    );
                  }}
                >
                  重新生成像素卡片
                </button>
              ) : (
                <button
                  className="secondary-action"
                  type="button"
                  onClick={() => {
                    setPixelTaskOpen(false);
                    setPixelTaskCollapsed(true);
                  }}
                >
                  收起到浮球
                </button>
              )}
            </motion.section>
          </motion.div>
        ) : null}
      </AnimatePresence>
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
  const [tryOnPhotoPickerOpen, setTryOnPhotoPickerOpen] = useState(false);

  useEffect(() => {
    setTryOnPhotoPickerOpen(false);
  }, [props.detail?.look.id]);

  const closeDetail = () => {
    setTryOnPhotoPickerOpen(false);
    props.onClose();
  };

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
            onClose={closeDetail}
            onReturnToSource={props.onReturnToSource}
            onRetry={props.onRetry}
            onSaveReason={props.onSaveReason}
            onGenerate={props.onGenerate}
            onSetPixelCover={props.onSetPixelCover}
            activePixelCoverId={props.activePixelCoverId}
            onTryOn={props.onTryOn}
            onDeleteTryOnPhoto={props.onDeleteTryOnPhoto}
            onDeleteSource={props.onDeleteSource}
            onDeleteLook={props.onDeleteLook}
            onAdvancePurchaseDemand={props.onAdvancePurchaseDemand}
            tryOnPhotoPickerOpen={tryOnPhotoPickerOpen}
            onOpenTryOnPicker={() => setTryOnPhotoPickerOpen(true)}
            onCloseTryOnPicker={() => setTryOnPhotoPickerOpen(false)}
          />
          <AnimatePresence>
            {tryOnPhotoPickerOpen && props.onTryOn ? (
              <TryOnPhotoSheet
                album={props.photoAlbum ?? emptyAlbum()}
                busy={props.tryOnUploading}
                onAlbumChange={props.onPhotoAlbumChange ?? (() => undefined)}
                onChoose={(file) => {
                  props.onTryOn?.(props.detail!.look.id, file);
                  setTryOnPhotoPickerOpen(false);
                }}
                onClose={() => setTryOnPhotoPickerOpen(false)}
              />
            ) : null}
          </AnimatePresence>
        </div>
      ) : null}
    </AnimatePresence>
  );
}
