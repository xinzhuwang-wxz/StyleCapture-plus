import { motion } from "motion/react";
import { useState } from "react";

export type CaptureCardState = "decide" | "saving" | "saved" | "error";

interface FeedCaptureCardProps {
  frameImageUrl: string;
  tagLabel: string;
  creatorName: string;
  state: CaptureCardState;
  errorMessage?: string | null;
  /** 单品类标签时展示「查看 AI 搭配」入口 */
  showAIEntry?: boolean;
  onSave: () => void;
  onDismiss: () => void;
  onViewAI?: () => void;
  onEnterMini?: () => void;
}

const SWIPE_THRESHOLD = 90;

/**
 * 圈选后弹出的高光卡片：
 * 右滑 → 存入数字衣橱；左滑 → 不存。
 */
export function FeedCaptureCard({
  frameImageUrl,
  tagLabel,
  creatorName,
  state,
  errorMessage,
  showAIEntry = false,
  onSave,
  onDismiss,
  onViewAI,
  onEnterMini
}: FeedCaptureCardProps) {
  const [dragX, setDragX] = useState(0);

  return (
    <div className="feed-capture-card-layer" role="dialog" aria-modal="true" aria-label="圈选结果">
      {/* 背景高光 */}
      <motion.div
        className="feed-capture-card-glow"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        aria-hidden="true"
      />

      {/* 左右滑动提示 */}
      {state === "decide" ? (
        <>
          <motion.div
            className="feed-capture-hint feed-capture-hint--left"
            animate={{ opacity: dragX < -20 ? 1 : 0.35 }}
            aria-hidden="true"
          >
            ✕ 不存
          </motion.div>
          <motion.div
            className="feed-capture-hint feed-capture-hint--right"
            animate={{ opacity: dragX > 20 ? 1 : 0.35 }}
            aria-hidden="true"
          >
            ⭐ 存入衣橱
          </motion.div>
        </>
      ) : null}

      <motion.div
        className={`feed-capture-card${dragX > 20 ? " is-save" : dragX < -20 ? " is-drop" : ""}`}
        initial={{ scale: 0.6, y: 60, opacity: 0 }}
        animate={{
          scale: state === "saved" ? 0.94 : 1,
          y: 0,
          opacity: 1,
          rotate: dragX / 24
        }}
        transition={{ type: "spring", stiffness: 320, damping: 26 }}
        drag={state === "decide" ? "x" : false}
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.7}
        onDrag={(_e, info) => setDragX(info.offset.x)}
        onDragEnd={(_e, info) => {
          setDragX(0);
          if (state !== "decide") return;
          if (info.offset.x >= SWIPE_THRESHOLD) onSave();
          else if (info.offset.x <= -SWIPE_THRESHOLD) onDismiss();
        }}
      >
        {/* 卡片图 */}
        <div className="feed-capture-card__image">
          <img src={frameImageUrl} alt={`圈选的${tagLabel}`} data-pixel="false" />
          <span className="feed-capture-card__tag">{tagLabel}</span>
        </div>

        {state === "decide" ? (
          <div className="feed-capture-card__body">
            <p className="feed-capture-card__title">圈到了 {tagLabel}！</p>
            <p className="feed-capture-card__subtitle">
              来自 @{creatorName} · 右滑存入数字衣橱，左滑不要
            </p>
            <div className="feed-capture-card__actions">
              <button type="button" className="feed-capture-btn feed-capture-btn--ghost" onClick={onDismiss}>
                ← 不存
              </button>
              <button type="button" className="feed-capture-btn feed-capture-btn--primary" onClick={onSave}>
                ⭐ 存入衣橱
              </button>
            </div>
            {showAIEntry && onViewAI ? (
              <button type="button" className="feed-capture-btn feed-capture-btn--ai" onClick={onViewAI}>
                🤖 查看 AI 搭配
              </button>
            ) : null}
          </div>
        ) : null}

        {state === "saving" ? (
          <div className="feed-capture-card__body feed-capture-card__body--center">
            <span className="feed-spinner" aria-hidden="true" />
            <p className="feed-capture-card__subtitle">正在存入数字衣橱…</p>
          </div>
        ) : null}

        {state === "error" ? (
          <div className="feed-capture-card__body feed-capture-card__body--center">
            <p className="feed-capture-card__title">😵 这次没存进去</p>
            <p className="feed-capture-card__subtitle">{errorMessage ?? "网络开小差了，再试一次"}</p>
            <div className="feed-capture-card__actions">
              <button type="button" className="feed-capture-btn feed-capture-btn--ghost" onClick={onDismiss}>
                放弃
              </button>
              <button type="button" className="feed-capture-btn feed-capture-btn--primary" onClick={onSave}>
                重试
              </button>
            </div>
          </div>
        ) : null}

        {state === "saved" ? (
          <div className="feed-capture-card__body feed-capture-card__body--center">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 400, damping: 15 }}
              style={{ fontSize: "2.6rem" }}
              aria-hidden="true"
            >
              ⭐
            </motion.div>
            <p className="feed-capture-card__title">已存入数字衣橱！</p>
            <p className="feed-capture-card__subtitle">继续刷，或去小程序里看看它</p>
            <div className="feed-capture-card__actions">
              <button type="button" className="feed-capture-btn feed-capture-btn--ghost" onClick={onDismiss}>
                继续刷
              </button>
              {onEnterMini ? (
                <button type="button" className="feed-capture-btn feed-capture-btn--primary" onClick={onEnterMini}>
                  👾 进入小程序
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
      </motion.div>
    </div>
  );
}
