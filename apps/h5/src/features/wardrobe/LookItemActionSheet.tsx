import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";

import type { Ownership } from "../../api/client";
import { buildDouyinSearchUrl } from "./purchaseSearch";

export type LookItemAction = {
  itemId: string | null;
  label: string;
  imageUrl: string | null;
  ownership: Ownership;
  purchaseSearchUrl: string | null;
};

type LookItemActionSheetProps = {
  action: LookItemAction | null;
  onClose: () => void;
  onBuildOutfit: (itemId: string) => void;
  onCheckCompatibility: (itemId: string | null) => void;
};

export function LookItemActionSheet({
  action,
  onClose,
  onBuildOutfit,
  onCheckCompatibility
}: LookItemActionSheetProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  const purchaseSearchUrl =
    action?.purchaseSearchUrl || buildDouyinSearchUrl(action?.label ?? "");

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!action) return;
    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    previousFocusRef.current = previousFocus;
    const scrollPositions: Array<{
      element: HTMLElement;
      scrollLeft: number;
      scrollTop: number;
    }> = [];
    let ancestor: HTMLElement | null = previousFocus;
    while (ancestor) {
      scrollPositions.push({
        element: ancestor,
        scrollLeft: ancestor.scrollLeft,
        scrollTop: ancestor.scrollTop
      });
      ancestor = ancestor.parentElement;
    }
    const restoreScrollPositions = () => {
      scrollPositions.forEach(({ element, scrollLeft, scrollTop }) => {
        if (!element.isConnected) return;
        element.scrollLeft = scrollLeft;
        element.scrollTop = scrollTop;
      });
    };
    closeButtonRef.current?.focus({ preventScroll: true });
    restoreScrollPositions();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      onCloseRef.current();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      window.setTimeout(() => {
        previousFocusRef.current?.focus({ preventScroll: true });
        restoreScrollPositions();
      }, 0);
    };
  }, [action]);

  return (
    <AnimatePresence>
      {action ? (
        <motion.div
          className="look-item-action-layer"
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={(event) => {
            if (event.target === event.currentTarget) onClose();
          }}
        >
          <motion.section
            className="look-item-action-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="look-item-action-title"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 340, damping: 34 }}
          >
            <div className="look-item-action-sheet__handle" aria-hidden="true" />
            <div className="look-item-action-sheet__heading">
              <div>
                <small>{action.ownership === "owned" ? "衣橱单品" : "穿搭灵感"}</small>
                <h2 id="look-item-action-title">{action.label}</h2>
              </div>
              <button
                ref={closeButtonRef}
                type="button"
                aria-label="关闭单品操作"
                onClick={onClose}
              >
                ×
              </button>
            </div>

            {action.imageUrl ? (
              <img
                className="look-item-action-sheet__image"
                src={action.imageUrl}
                alt={`${action.label}实物图`}
              />
            ) : null}

            <div className="look-item-action-sheet__actions">
              {action.ownership === "owned" ? (
                <button
                  className="primary-action"
                  type="button"
                  disabled={!action.itemId}
                  onClick={() => action.itemId && onBuildOutfit(action.itemId)}
                >
                  用这件搭一套
                </button>
              ) : (
                <>
                  <a
                    className="primary-action"
                    href={purchaseSearchUrl}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    未拥有，去购买
                  </a>
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() => onCheckCompatibility(action.itemId)}
                  >
                    检测与已有穿搭的适配度
                  </button>
                </>
              )}
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
