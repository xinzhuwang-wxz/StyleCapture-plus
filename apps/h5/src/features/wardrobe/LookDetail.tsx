import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import type { LookDetail as LookDetailData } from "../../api/client";

type LookDetailProps = {
  detail: LookDetailData | null;
  loading: boolean;
  retrying: boolean;
  saving: boolean;
  onClose: () => void;
  onReturnToSource: (videoRef: string, timestampMs: number) => void;
  onRetry: (lookId: string) => void;
  onSaveReason: (lookId: string, reason: string) => void;
};

function DetailContent({
  detail,
  retrying,
  saving,
  onClose,
  onReturnToSource,
  onRetry,
  onSaveReason
}: Omit<LookDetailProps, "detail" | "loading"> & {
  detail: LookDetailData;
}) {
  const [reason, setReason] = useState("");
  const values = detail.analysis?.values ?? {};
  const heroImageUrl =
    detail.look.source_image_url ?? detail.look.display_image_url;

  useEffect(() => {
    setReason("");
  }, [detail.look.id]);

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
        <button className="icon-button" type="button" aria-label="返回衣橱" onClick={onClose}>
          ‹
        </button>
        <strong id="look-detail-title">穿搭详情</strong>
        <span className="detail-topbar__spacer" />
      </div>

      <div className="detail-image look-detail__hero">
        {heroImageUrl ? (
          <img
            src={heroImageUrl}
            alt="收藏的真实整套穿搭"
          />
        ) : (
          <div className="item-image-placeholder">
            <span>✦</span>
            <small>原始画面已删除</small>
          </div>
        )}
        {detail.look.status === "processing" ? (
          <div className="look-detail__processing">
            <strong>整套已收藏</strong>
            <span>AI 正在后台拆解真实单品</span>
          </div>
        ) : null}
      </div>

      <div className="detail-content">
        <div className="detail-meta">
          <span>
            {detail.look.source_available ? "真实 Feed 来源" : "来源画面已删除"}
          </span>
          <span>
            {detail.look.status === "ready" ? "搭配分析完成" : "后台处理中"}
          </span>
        </div>

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
        ) : detail.source_video_ref ? (
          <p className="source-unavailable" role="status">
            原始画面已删除，穿搭关系和已拆出的单品仍保留。
          </p>
        ) : null}

        {detail.components.length > 0 ? (
          <section className="look-detail__section" aria-labelledby="look-components-title">
            <div className="section-heading">
              <h3 id="look-components-title">这套里的单品</h3>
              <span>{detail.components.length} 件</span>
            </div>
            <div className="look-component-strip">
              {detail.components.map((component) => (
                <article key={component.component_key}>
                  {component.item_image_url ? (
                    <img src={component.item_image_url} alt={component.role ?? "穿搭单品"} />
                  ) : (
                    <div className="item-image-placeholder">
                      <span>衣</span>
                    </div>
                  )}
                  <strong>{component.role ?? component.layer ?? "待识别单品"}</strong>
                  <small>
                    {component.item_id ? "已进入单品衣橱" : "保留中，等待补全"}
                  </small>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {detail.analysis ? (
          <section className="look-detail__section" aria-labelledby="look-analysis-title">
            <div className="section-heading">
              <h3 id="look-analysis-title">搭配关系</h3>
              <span>AI 理解</span>
            </div>
            <div className="look-analysis">
              {Object.entries(values).map(([key, value]) => (
                <p key={key}>
                  <span>{key}</span>
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
            retrying={props.retrying}
            saving={props.saving}
            onClose={props.onClose}
            onReturnToSource={props.onReturnToSource}
            onRetry={props.onRetry}
            onSaveReason={props.onSaveReason}
          />
        </div>
      ) : null}
    </AnimatePresence>
  );
}
