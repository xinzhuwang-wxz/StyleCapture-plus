import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import type { Ownership, SourceKind } from "../../api/client";

type SelectedImage = {
  file: File;
  previewUrl: string | null;
  sourceKind: SourceKind;
};

type CaptureSheetProps = {
  selection: SelectedImage | null;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (
    ownership: Ownership,
    intent: "item" | "whole_outfit"
  ) => void;
};

export function CaptureSheet({
  selection,
  busy,
  error,
  onCancel,
  onConfirm
}: CaptureSheetProps) {
  const [ownership, setOwnership] = useState<Ownership | null>(
    selection?.sourceKind === "feed" ? "inspiration" : "owned"
  );
  const [intent, setIntent] = useState<"item" | "whole_outfit" | null>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const busyRef = useRef(busy);
  const onCancelRef = useRef(onCancel);
  const browserCanPreviewSelection = selection
    ? canBrowserPreview(selection.file)
    : false;

  useEffect(() => {
    busyRef.current = busy;
    onCancelRef.current = onCancel;
  }, [busy, onCancel]);

  useEffect(() => {
    if (!selection) return;
    setOwnership(selection.sourceKind === "feed" ? "inspiration" : "owned");
    setIntent(null);
    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (dialogRef.current) dialogRef.current.scrollTop = 0;
    cancelButtonRef.current?.focus({ preventScroll: true });
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busyRef.current) {
        event.preventDefault();
        onCancelRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        ) ?? []
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.setTimeout(
        () => previousFocusRef.current?.focus({ preventScroll: true }),
        0
      );
    };
  }, [selection]);

  return (
    <AnimatePresence>
      {selection ? (
        <motion.div
          className="pixel-sheet"
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={(e) => {
            if (e.target === e.currentTarget) onCancel();
          }}
        >
          <motion.section
            ref={dialogRef}
            className="pixel-sheet__content capture-sheet__content"
            role="dialog"
            aria-modal="true"
            aria-labelledby="capture-sheet-title"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 330, damping: 34 }}
          >
            {/* Handle */}
            <div
              className="capture-sheet__handle"
              aria-hidden="true"
            />

            {/* Header */}
            <div className="capture-sheet__header">
              <div>
                <p className="capture-sheet__eyebrow">最后一步</p>
                <h2
                  id="capture-sheet-title"
                  className="capture-sheet__title"
                >
                  确认加入衣橱
                </h2>
              </div>
              <button
                ref={cancelButtonRef}
                type="button"
                className="capture-sheet__close"
                aria-label="取消入库"
                disabled={busy}
                onClick={onCancel}
              >
                ×
              </button>
            </div>

            {/* Preview */}
            <div className="capture-sheet__preview">
              {browserCanPreviewSelection && selection.previewUrl ? (
                <img
                  src={selection.previewUrl}
                  alt="待加入衣橱的衣服"
                  className="capture-sheet__preview-image"
                />
              ) : (
                <div className="capture-heic-preview" role="status">
                  <span aria-hidden="true">✦</span>
                  <strong>iPhone 照片已选中</strong>
                  <small>上传后会先转成可展示的真实图片，再进入识别和像素化</small>
                </div>
              )}
              <span className="capture-sheet__source">
                {selection.sourceKind === "camera" ? "📷 刚刚拍摄" : "🖼️ 来自相册"}
              </span>
            </div>

            <fieldset
              disabled={busy}
              className="capture-sheet__fieldset"
            >
              <legend className="capture-sheet__legend">
                这张图要保存成什么？
              </legend>
              <div className="capture-kind-options">
                <button
                  type="button"
                  className={intent === "item" ? "is-selected" : ""}
                  aria-pressed={intent === "item"}
                  onClick={() => setIntent("item")}
                >
                  <strong>单件衣服</strong>
                  <small>提取并标准化单品实物图，归入单品分类</small>
                </button>
                <button
                  type="button"
                  className={intent === "whole_outfit" ? "is-selected" : ""}
                  aria-pressed={intent === "whole_outfit"}
                  onClick={() => setIntent("whole_outfit")}
                >
                  <strong>整套穿搭</strong>
                  <small>拆成多件单品，并生成像素小人</small>
                </button>
              </div>
            </fieldset>

            {/* Ownership Selection */}
            <fieldset
              disabled={busy}
              className="capture-sheet__fieldset capture-sheet__fieldset--ownership"
            >
              <legend className="capture-sheet__legend">
                这件衣服属于哪里？
              </legend>
              <div className="capture-sheet__ownership-options">
                <button
                  type="button"
                  className={`capture-sheet__ownership-option${ownership === "owned" ? " is-selected" : ""}`}
                  aria-pressed={ownership === "owned"}
                  onClick={() => setOwnership("owned")}
                >
                  <span aria-hidden="true">☆</span>
                  <strong>已拥有</strong>
                </button>
                <button
                  type="button"
                  className={`capture-sheet__ownership-option${ownership === "inspiration" ? " is-selected" : ""}`}
                  aria-pressed={ownership === "inspiration"}
                  onClick={() => setOwnership("inspiration")}
                >
                  <span aria-hidden="true">💞</span>
                  <strong>待拥有</strong>
                </button>
              </div>
            </fieldset>

            {error ? (
              <p className="capture-sheet__error" role="alert">
                ⚠️ {error}
              </p>
            ) : null}

            <div className="capture-sheet__footer">
              <button
                type="button"
                className="capture-sheet__submit"
                disabled={!ownership || !intent || busy}
                onClick={() => ownership && intent && onConfirm(ownership, intent)}
              >
                {busy
                  ? "🔄 正在入库…"
                  : intent === "whole_outfit"
                    ? "✦ 保存整套并生成像素小人"
                    : intent === "item"
                      ? "⭐ 加入单品衣橱"
                      : "请选择保存类型"}
              </button>
              <p className="capture-sheet__hint">
                原图仅用于你的数字衣橱，可随时删除
              </p>
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function canBrowserPreview(file: File): boolean {
  const type = contentTypeFor(file);
  return type === "image/jpeg" || type === "image/png" || type === "image/webp";
}

function contentTypeFor(file: File): string {
  if (file.type) return file.type.toLowerCase();
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension === "heic") return "image/heic";
  if (extension === "heif") return "image/heif";
  if (extension === "jpg" || extension === "jpeg") return "image/jpeg";
  if (extension === "png") return "image/png";
  if (extension === "webp") return "image/webp";
  return "";
}
