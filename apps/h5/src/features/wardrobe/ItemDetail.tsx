import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { wardrobeApi, type Item, type ItemPresentation, type Ownership } from "../../api/client";
import {
  GARMENT_CATEGORY_OPTIONS,
  garmentLabel,
  sourceKindLabel
} from "./localization";
import { buildDouyinSearchUrl } from "./purchaseSearch";
import { useDisplayImage } from "./useDisplayImage";
import { DeleteAssetDialog } from "./DeleteAssetDialog";

type ItemDetailProps = {
  item: Item | null;
  saving: boolean;
  deleting?: boolean;
  onClose: () => void;
  onSave: (
    itemId: string,
    changes: {
      ownership?: Ownership;
      corrections?: Record<string, string>;
    }
  ) => void;
  onDeleteSource: (itemId: string) => void;
  onDeleteItem?: (itemId: string) => void;
  onBuildOutfit: (itemId: string) => void;
  onReturnToFeed: (videoRef: string, timestampMs: number) => void;
};

function DetailContent({
  item,
  saving,
  deleting = false,
  onClose,
  onSave,
  onDeleteSource,
  onDeleteItem,
  onBuildOutfit,
  onReturnToFeed
}: Omit<ItemDetailProps, "item"> & { item: Item }) {
  const imageUrl = useDisplayImage(item.id, `${item.status}:${item.updated_at}`);
  const sourceImageUrl = useDisplayImage(
    item.id,
    `${item.status}:${item.updated_at}:source`,
    !item.source_available,
    "source"
  );
  const [ownership, setOwnership] = useState<Ownership>(item.ownership);
  const [category, setCategory] = useState(String(item.attributes.category?.value ?? ""));
  const description = String(item.attributes.description?.value ?? "");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deletingItemOpen, setDeletingItemOpen] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const [flatLay, setFlatLay] = useState<ItemPresentation | null>(null);
  const [flatLayError, setFlatLayError] = useState<string | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const onCloseRef = useRef(onClose);
  const purchaseSearchQuery =
    item.purchase_search_query ||
    String(item.attributes.description?.value ?? "").trim() ||
    String(item.attributes.subcategory?.value ?? "").trim() ||
    garmentLabel(String(item.attributes.category?.value ?? "")) ||
    "同款穿搭单品";
  const purchaseSearchUrl =
    item.purchase_search_url || buildDouyinSearchUrl(purchaseSearchQuery);

  const displayImageNote =
    item.display_image_kind === "derived_garment"
      ? "当前展示已标准化的单品实物图；像素图只用于衣橱封面。"
      : item.display_image_issue === "multiple_garments"
        ? "照片里识别到多件衣服。为避免抠错，当前保留原图；录入单品请重新上传只包含一件衣服的正面照片，保存全身搭配请选择“整套穿搭”。"
        : item.display_image_issue === "no_reliable_garment"
          ? "这张照片里暂未可靠定位到单件衣物。为避免抠错，当前保留原图；建议重新上传清晰的单件衣物正面照。"
          : item.display_image_issue === "normalization_unavailable"
            ? "单品抠图暂时未完成，当前展示原图；标签与搭配仍可使用。"
            : "当前展示上传原图；像素图只用于衣橱封面。";

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    setOwnership(item.ownership);
    setCategory(String(item.attributes.category?.value ?? ""));
    setConfirmingDelete(false);
    setDeletingItemOpen(false);
    setImageFailed(false);
  }, [item]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    async function loadFlatLay() {
      try {
        const presentation = await wardrobeApi.ensureItemFlatLayPresentation(item.id);
        if (cancelled) return;
        setFlatLay(presentation);
        setFlatLayError(null);
        if (presentation.status === "queued" || presentation.status === "running") {
          timer = window.setTimeout(() => void loadFlatLay(), 1_500);
        }
      } catch (error) {
        if (!cancelled) {
          setFlatLayError(error instanceof Error ? error.message : "真实单品白底图暂时无法生成");
        }
      }
    }
    setFlatLay(null);
    setFlatLayError(null);
    void loadFlatLay();
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [item.id, item.updated_at]);

  const flatLayReady = flatLay?.status === "succeeded" && Boolean(flatLay.output_image_url);
  const hasStandardizedDisplay =
    item.display_image_kind === "derived_garment" && Boolean(imageUrl);
  const flatLayGenerating =
    flatLayError === null &&
    (flatLay === null || flatLay.status === "queued" || flatLay.status === "running");
  const heroImageUrl = flatLayReady
    ? flatLay.output_image_url
    : flatLayGenerating
      ? sourceImageUrl ?? imageUrl
      : imageUrl;

  useEffect(() => {
    if (heroImageUrl) {
      setImageFailed(false);
    }
  }, [heroImageUrl]);

  useEffect(() => {
    const previouslyFocused = document.activeElement;
    closeButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (deletingItemOpen) setDeletingItemOpen(false);
        else onCloseRef.current();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (previouslyFocused instanceof HTMLElement && previouslyFocused.isConnected) {
        previouslyFocused.focus();
      }
    };
  }, [deletingItemOpen, item.id]);

  return (
    <motion.section
      className="detail-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="item-detail-title"
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
        <strong id="item-detail-title">单品详情</strong>
        {onDeleteItem ? (
          <button
            className="icon-button detail-delete-button"
            type="button"
            aria-label="删除单品"
            onClick={() => setDeletingItemOpen(true)}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5" />
            </svg>
          </button>
        ) : (
          <span className="detail-topbar__spacer" />
        )}
      </div>

      <div
        className="detail-image"
        data-flat-lay={flatLayReady ? "true" : undefined}
        data-generating={flatLayGenerating ? "true" : undefined}
      >
        {heroImageUrl && !imageFailed ? (
          <img
            src={heroImageUrl}
            alt={flatLayReady ? `${description || "衣橱单品"}的白底平铺图` : description || "衣橱单品原图"}
            onError={() => setImageFailed(true)}
            data-image-kind={
              flatLayReady
                ? "generated-flat-lay"
                : flatLayGenerating && sourceImageUrl
                  ? "wardrobe-source-fallback"
                  : item.display_image_kind === "derived_garment"
                  ? "wardrobe-display"
                  : "wardrobe-source-fallback"
            }
          />
        ) : (
          <div className="item-image-placeholder">
            <span>衣</span>
            <small>
              {imageFailed ? "图片格式暂不可预览，识别结果仍保留" : "原图已删除或不可用"}
            </small>
          </div>
        )}
        {flatLayGenerating ? (
          <div className="item-flat-lay-loading" role="status" aria-live="polite">
            <span className="item-flat-lay-spinner" aria-hidden="true" />
            <strong>正在生成单品图</strong>
            <small>完成后会自动替换当前原图</small>
          </div>
        ) : null}
      </div>

      <div className="detail-content">
        <p className="flat-lay-status" role="status">
          {flatLayReady
            ? "真实单品白底图 · 3:4"
            : flatLayGenerating
              ? "正在生成单品图…"
              : hasStandardizedDisplay
                ? "单品图已生成"
                : flatLayError ?? "当前展示识别图；白底单品图暂不可用"}
        </p>
        {flatLayReady && (sourceImageUrl ?? imageUrl) ? (
          <details className="flat-lay-source">
            <summary>查看识别来源图</summary>
            <img
              src={sourceImageUrl ?? imageUrl ?? undefined}
              alt={`${description || "衣橱单品"}的识别来源图`}
            />
          </details>
        ) : null}
        <div className="detail-meta">
          <span>{sourceKindLabel(item.source_kind)}</span>
          <span>{item.status === "ready" ? "已完成理解" : "仍可编辑"}</span>
        </div>
        {item.source_kind === "feed" ? (
          item.source_video_ref && item.source_timestamp_ms !== null ? (
            <button
              className="secondary-action"
              type="button"
              onClick={() =>
                onReturnToFeed(item.source_video_ref!, item.source_timestamp_ms!)
              }
            >
              回看 Feed 来源
            </button>
          ) : (
            <p className="privacy-note">来源视频暂不可回看，已保存的单品不受影响。</p>
          )
        ) : null}

        <p
          className={`display-image-note${
            item.display_image_kind === "derived_garment"
              ? ""
              : " display-image-note--attention"
          }`}
          role="status"
        >
          {displayImageNote}
        </p>

        <label className="form-field">
          <span>分类</span>
          <select
            value={category}
            aria-label="分类"
            disabled={saving}
            onChange={(event) => {
              const nextCategory = event.target.value;
              setCategory(nextCategory);
              if (nextCategory.trim()) {
                onSave(item.id, { corrections: { category: nextCategory.trim() } });
              }
            }}
          >
            <option value="">待分类</option>
            {GARMENT_CATEGORY_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {garmentLabel(option)}
              </option>
            ))}
          </select>
          {category &&
          !GARMENT_CATEGORY_OPTIONS.includes(
            category as (typeof GARMENT_CATEGORY_OPTIONS)[number]
          ) ? (
            <small>当前分类：{garmentLabel(category)}</small>
          ) : null}
        </label>
        <div className="segmented-control" aria-label="是否已拥有">
          <button
            type="button"
            className={ownership === "owned" ? "is-selected" : ""}
            disabled={saving}
            onClick={() => {
              setOwnership("owned");
              onSave(item.id, { ownership: "owned" });
            }}
          >
            已拥有
          </button>
          <button
            type="button"
            className={ownership === "inspiration" ? "is-selected" : ""}
            disabled={saving}
            onClick={() => {
              setOwnership("inspiration");
              onSave(item.id, { ownership: "inspiration" });
            }}
          >
            待拥有
          </button>
        </div>

        <div className="item-detail__action-row">
          <button
            className="secondary-action"
            type="button"
            onClick={() => onBuildOutfit(item.id)}
          >
            用这件搭一套
          </button>
          <a
            className="item-detail__shop-button"
            href={purchaseSearchUrl}
            target="_blank"
            rel="noreferrer noopener"
            aria-label={`去抖音商城搜索${purchaseSearchQuery}`}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <path d="M3.5 4.5h2l1.6 9.1a2 2 0 0 0 2 1.7h7.8a2 2 0 0 0 2-1.6l1.1-5.8H7" />
              <circle cx="9.5" cy="19" r="1.25" />
              <circle cx="17.5" cy="19" r="1.25" />
            </svg>
          </a>
        </div>
        {!item.source_available ? (
          <p className="privacy-note">
            原始上传图已删除；标准化单品图、标签和描述仍保留并可继续使用。
          </p>
        ) : confirmingDelete ? (
          <div className="delete-confirmation" role="alert">
            <p>
              删除后原始上传图无法恢复；标准化单品图、分类、描述和归属仍会保留。
            </p>
            <div>
              <button type="button" onClick={() => setConfirmingDelete(false)}>
                保留原图
              </button>
              <button type="button" onClick={() => onDeleteSource(item.id)}>
                确认删除原图
              </button>
            </div>
          </div>
        ) : (
          <button
            className="danger-link"
            type="button"
            onClick={() => setConfirmingDelete(true)}
          >
            删除原图
          </button>
        )}
      </div>
      <DeleteAssetDialog
        kind="item"
        open={deletingItemOpen}
        busy={deleting}
        onClose={() => setDeletingItemOpen(false)}
        onConfirm={() => onDeleteItem?.(item.id)}
      />
    </motion.section>
  );
}

export function ItemDetail(props: ItemDetailProps) {
  return (
    <AnimatePresence>
      {props.item ? (
        <div className="detail-layer detail-layer--item">
          <DetailContent {...props} item={props.item} />
        </div>
      ) : null}
    </AnimatePresence>
  );
}
