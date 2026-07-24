import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import type { Ownership, SourceKind } from "../../api/client";

type SelectedImage = {
  file: File;
  previewUrl: string;
  sourceKind: SourceKind;
};

type CaptureSheetProps = {
  selection: SelectedImage | null;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (ownership: Ownership) => void;
};

export function CaptureSheet({
  selection,
  busy,
  error,
  onCancel,
  onConfirm
}: CaptureSheetProps) {
  const [ownership, setOwnership] = useState<Ownership | null>(null);

  return (
    <AnimatePresence>
      {selection ? (
        <motion.div
          className="sheet-backdrop"
          role="presentation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.section
            className="capture-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="capture-sheet-title"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 330, damping: 34 }}
          >
            <div className="sheet-handle" aria-hidden="true" />
            <div className="sheet-heading">
              <div>
                <p className="section-kicker">最后一步</p>
                <h2 id="capture-sheet-title">确认加入衣橱</h2>
              </div>
              <button
                className="icon-button"
                type="button"
                aria-label="取消入库"
                disabled={busy}
                onClick={onCancel}
              >
                ×
              </button>
            </div>

            <div className="capture-preview">
              <img src={selection.previewUrl} alt="待加入衣橱的衣服" />
              <span>{selection.sourceKind === "camera" ? "刚刚拍摄" : "来自相册"}</span>
            </div>

            <fieldset className="ownership-fieldset" disabled={busy}>
              <legend>这件衣服属于哪里？</legend>
              <div className="ownership-options">
                <button
                  className={ownership === "owned" ? "ownership-option is-selected" : "ownership-option"}
                  type="button"
                  aria-pressed={ownership === "owned"}
                  onClick={() => setOwnership("owned")}
                >
                  <span aria-hidden="true">衣</span>
                  <strong>我的衣服</strong>
                  <small>已经拥有，可以直接参与搭配</small>
                </button>
                <button
                  className={
                    ownership === "inspiration"
                      ? "ownership-option is-selected"
                      : "ownership-option"
                  }
                  type="button"
                  aria-pressed={ownership === "inspiration"}
                  onClick={() => setOwnership("inspiration")}
                >
                  <span aria-hidden="true">✦</span>
                  <strong>穿搭灵感</strong>
                  <small>还没拥有，先收藏以后搭配</small>
                </button>
              </div>
            </fieldset>

            {error ? (
              <p className="inline-error" role="alert">
                {error}
              </p>
            ) : null}

            <button
              className="primary-action"
              type="button"
              disabled={!ownership || busy}
              onClick={() => ownership && onConfirm(ownership)}
            >
              {busy ? "正在安全入库…" : "加入衣橱"}
            </button>
            <p className="privacy-note">原图仅用于你的数字衣橱，可随时删除。</p>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
