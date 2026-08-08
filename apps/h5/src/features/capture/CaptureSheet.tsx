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
    cancelButtonRef.current?.focus();
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
      window.setTimeout(() => previousFocusRef.current?.focus(), 0);
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
            className="pixel-sheet__content"
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
              style={{
                width: "3rem",
                height: "4px",
                margin: "0 auto var(--px-4)",
                background: "var(--pixel-border)"
              }}
              aria-hidden="true"
            />

            {/* Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "var(--px-4)"
              }}
            >
              <div>
                <p className="pixel-label">最后一步</p>
                <h2
                  id="capture-sheet-title"
                  className="pixel-subtitle"
                  style={{ color: "var(--pixel-text)" }}
                >
                  确认加入衣橱
                </h2>
              </div>
              <button
                ref={cancelButtonRef}
                type="button"
                className="pixel-button pixel-button--ghost"
                style={{ width: "2.5rem", height: "2.5rem", padding: 0 }}
                aria-label="取消入库"
                disabled={busy}
                onClick={onCancel}
              >
                ×
              </button>
            </div>

            {/* Preview */}
            <div
              style={{
                position: "relative",
                height: "12rem",
                border: "3px solid var(--pixel-border)",
                boxShadow: "4px 4px 0 rgba(0,0,0,0.3)",
                overflow: "hidden",
                marginBottom: "var(--px-4)",
                background: "var(--pixel-surface-raised)"
              }}
            >
              {browserCanPreviewSelection && selection.previewUrl ? (
                <img
                  src={selection.previewUrl}
                  alt="待加入衣橱的衣服"
                  style={{ width: "100%", height: "100%", objectFit: "contain" }}
                />
              ) : (
                <div className="capture-heic-preview" role="status">
                  <span aria-hidden="true">✦</span>
                  <strong>iPhone 照片已选中</strong>
                  <small>上传后会先转成可展示的真实图片，再进入识别和像素化</small>
                </div>
              )}
              <span
                style={{
                  position: "absolute",
                  bottom: "var(--px-2)",
                  right: "var(--px-2)",
                  padding: "var(--px-1) var(--px-3)",
                  fontFamily: "var(--font-pixel)",
                  fontSize: "0.65rem",
                  background: "var(--pixel-surface)",
                  border: "2px solid var(--pixel-border)",
                  color: "var(--pixel-text-muted)"
                }}
              >
                {selection.sourceKind === "camera" ? "📷 刚刚拍摄" : "🖼️ 来自相册"}
              </span>
            </div>

            <fieldset
              disabled={busy}
              style={{ border: "none", padding: 0, margin: "0 0 var(--px-4)" }}
            >
              <legend
                style={{
                  fontFamily: "var(--font-pixel)",
                  fontSize: "0.75rem",
                  color: "var(--pixel-text-muted)",
                  marginBottom: "var(--px-3)"
                }}
              >
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
              style={{ border: "none", padding: 0, margin: 0 }}
            >
              <legend
                style={{
                  fontFamily: "var(--font-pixel)",
                  fontSize: "0.75rem",
                  color: "var(--pixel-text-muted)",
                  marginBottom: "var(--px-3)",
                  display: "block"
                }}
              >
                这件衣服属于哪里？
              </legend>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "var(--px-3)",
                  marginBottom: "var(--px-4)"
                }}
              >
                <button
                  type="button"
                  className="pixel-button"
                  style={{
                    flexDirection: "column",
                    padding: "var(--px-3) var(--px-3)",
                    minHeight: "4.8rem",
                    alignItems: "flex-start",
                    gap: "0.2rem",
                    background:
                      ownership === "owned"
                        ? "var(--pixel-accent)"
                        : "var(--pixel-surface-raised)",
                    borderColor:
                      ownership === "owned"
                        ? "var(--pixel-accent-glow)"
                        : "var(--pixel-border)",
                    color:
                      ownership === "owned"
                        ? "var(--pixel-surface)"
                        : "var(--pixel-text)"
                  }}
                  aria-pressed={ownership === "owned"}
                  onClick={() => setOwnership("owned")}
                >
                  <span style={{ fontSize: "1.25rem", lineHeight: 1 }}>⭐</span>
                  <strong style={{ fontSize: "0.72rem", lineHeight: 1.2 }}>已拥有</strong>
                  <small
                    style={{
                      fontSize: "0.55rem",
                      opacity: 0.7,
                      fontFamily: "var(--font-body)",
                      lineHeight: 1.3
                    }}
                  >
                    已拥有，可参与搭配
                  </small>
                </button>
                <button
                  type="button"
                  className="pixel-button"
                  style={{
                    flexDirection: "column",
                    padding: "var(--px-3) var(--px-3)",
                    minHeight: "4.8rem",
                    alignItems: "flex-start",
                    gap: "0.2rem",
                    background:
                      ownership === "inspiration"
                        ? "var(--pixel-primary)"
                        : "var(--pixel-surface-raised)",
                    borderColor:
                      ownership === "inspiration"
                        ? "var(--pixel-primary-dark)"
                        : "var(--pixel-border)",
                    color:
                      ownership === "inspiration" ? "#fff" : "var(--pixel-text)"
                  }}
                  aria-pressed={ownership === "inspiration"}
                  onClick={() => setOwnership("inspiration")}
                >
                  <span style={{ fontSize: "1.25rem", lineHeight: 1 }}>💖</span>
                  <strong style={{ fontSize: "0.72rem", lineHeight: 1.2 }}>待拥有</strong>
                  <small
                    style={{
                      fontSize: "0.55rem",
                      opacity: 0.7,
                      fontFamily: "var(--font-body)",
                      lineHeight: 1.3
                    }}
                  >
                    先收藏，以后搭配
                  </small>
                </button>
              </div>
            </fieldset>

            {error ? (
              <p
                style={{
                  color: "var(--pixel-error)",
                  fontFamily: "var(--font-pixel)",
                  fontSize: "0.75rem",
                  marginBottom: "var(--px-3)"
                }}
                role="alert"
              >
                ⚠️ {error}
              </p>
            ) : null}

            <button
              type="button"
              className="pixel-button pixel-button--primary w-full"
              disabled={!ownership || !intent || busy}
              onClick={() => ownership && intent && onConfirm(ownership, intent)}
              style={{ marginBottom: "var(--px-3)", fontSize: "0.78rem" }}
            >
              {busy
                ? "🔄 正在入库…"
                : intent === "whole_outfit"
                  ? "✦ 保存整套并生成像素小人"
                  : intent === "item"
                    ? "⭐ 加入单品衣橱"
                    : "请选择保存类型"}
            </button>
            <p
              style={{
                textAlign: "center",
                fontSize: "0.6rem",
                color: "var(--pixel-text-dim)",
                fontFamily: "var(--font-pixel)"
              }}
            >
              原图仅用于你的数字衣橱，可随时删除
            </p>
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
