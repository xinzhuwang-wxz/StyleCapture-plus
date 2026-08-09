import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

export type LookDeleteScope = "look_only" | "look_and_items";

type DeleteAssetDialogProps = {
  kind: "item" | "look";
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onConfirm: (scope?: LookDeleteScope) => void;
};

export function DeleteAssetDialog({
  kind,
  open,
  busy,
  onClose,
  onConfirm
}: DeleteAssetDialogProps) {
  const [scope, setScope] = useState<LookDeleteScope | null>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) {
      setScope(null);
      return;
    }
    const timer = window.setTimeout(
      () => cancelButtonRef.current?.focus({ preventScroll: true }),
      0
    );
    return () => window.clearTimeout(timer);
  }, [open, scope]);

  const itemConfirmation = kind === "item";
  const showingFinalConfirmation = itemConfirmation || scope !== null;

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="asset-delete-layer"
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={(event) => {
            if (!busy && event.target === event.currentTarget) onClose();
          }}
        >
          <motion.section
            className="asset-delete-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="asset-delete-title"
            aria-describedby="asset-delete-description"
            initial={{ y: 28, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 28, opacity: 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
          >
            <span className="asset-delete-dialog__symbol" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5" />
              </svg>
            </span>

            {showingFinalConfirmation ? (
              <>
                <h2 id="asset-delete-title">
                  {itemConfirmation
                    ? "确认删除这件单品？"
                    : scope === "look_only"
                      ? "确认仅删除此搭配？"
                      : "确认删除搭配和单品？"}
                </h2>
                <p id="asset-delete-description">
                  {itemConfirmation
                    ? "删除后，这件单品的图片、分析结果和衣橱记录都会被移除，且无法恢复。"
                    : scope === "look_only"
                      ? "只会删除这套搭配，搭配中的单品仍会保留在数字衣橱。"
                      : "这套搭配和仅属于它的单品会从数字衣橱移除；仍被其他搭配使用的单品会保留。此操作无法恢复。"}
                </p>
                <div className="asset-delete-dialog__actions">
                  <button
                    ref={cancelButtonRef}
                    className="secondary-action"
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      if (itemConfirmation) onClose();
                      else setScope(null);
                    }}
                  >
                    {itemConfirmation ? "取消" : "返回选择"}
                  </button>
                  <button
                    className="asset-delete-dialog__danger"
                    type="button"
                    disabled={busy}
                    onClick={() => onConfirm(scope ?? undefined)}
                  >
                    {busy ? "正在删除…" : "确认删除"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2 id="asset-delete-title">删除这套穿搭</h2>
                <p id="asset-delete-description">
                  请选择是否同时删除这套搭配里的单品。下一步还会请你最终确认。
                </p>
                <div className="asset-delete-dialog__choices">
                  <button type="button" onClick={() => setScope("look_only")}>
                    <strong>仅删除此搭配</strong>
                    <small>搭配中的单品继续保留</small>
                    <span aria-hidden="true">›</span>
                  </button>
                  <button type="button" onClick={() => setScope("look_and_items")}>
                    <strong>搭配和单品都删除</strong>
                    <small>移除仅属于此搭配的单品，共用单品会保留</small>
                    <span aria-hidden="true">›</span>
                  </button>
                </div>
                <button
                  ref={cancelButtonRef}
                  className="asset-delete-dialog__cancel"
                  type="button"
                  onClick={onClose}
                >
                  取消
                </button>
              </>
            )}
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
