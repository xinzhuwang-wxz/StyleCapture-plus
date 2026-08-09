import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";

type ItemChangeConfirmationDialogProps = {
  open: boolean;
  busy: boolean;
  title: string;
  description: string;
  onClose: () => void;
  onConfirm: () => void;
};

/** A reversible confirmation step for changes that alter a wardrobe record. */
export function ItemChangeConfirmationDialog({
  open,
  busy,
  title,
  description,
  onClose,
  onConfirm
}: ItemChangeConfirmationDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(
      () => cancelRef.current?.focus({ preventScroll: true }),
      0
    );
    return () => window.clearTimeout(timer);
  }, [open]);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="item-change-layer"
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={(event) => {
            if (!busy && event.target === event.currentTarget) onClose();
          }}
        >
          <motion.section
            className="item-change-dialog"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="item-change-title"
            aria-describedby="item-change-description"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
          >
            <span className="item-change-dialog__symbol" aria-hidden="true">✦</span>
            <h2 id="item-change-title">{title}</h2>
            <p id="item-change-description">{description}</p>
            <div className="item-change-dialog__actions">
              <button
                ref={cancelRef}
                className="secondary-action"
                type="button"
                disabled={busy}
                onClick={onClose}
              >
                取消
              </button>
              <button
                className="primary-action"
                type="button"
                disabled={busy}
                onClick={onConfirm}
              >
                {busy ? "正在保存…" : "确认切换"}
              </button>
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
