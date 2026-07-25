import type { RenderArtifact, TryOnArtifact } from "../render/domain/renderArtifact";
import { tryOnLabel } from "../render/domain/renderArtifact";

/**
 * 穿搭详情页右侧的真人试穿面板。
 *
 * Issue #5 的诚实性要求全部落在这个组件里：
 * - processing：显示生成中的骨架，不先摆一张假图。
 * - ready + 用户参考照：才可以叫「AI 真人试穿」。
 * - ready + 固定模特：必须标注不是本人。
 * - degraded / error：回落到真实拼贴，并说明为什么没有试穿，
 *   绝不把降级结果标成生成成功。
 */
export function TryOnPane({
  tryOn,
  collage,
  revealed,
  onToggleReveal
}: {
  tryOn: TryOnArtifact;
  collage: RenderArtifact;
  /** 试穿图默认虚化，点击后展示（沿用设计稿的交互） */
  revealed: boolean;
  onToggleReveal: () => void;
}) {
  const label = tryOnLabel(tryOn);

  if (tryOn.status === "processing") {
    return (
      <div className="tryon-pane tryon-pane--busy" role="status">
        <span className="tryon-pane__spinner" aria-hidden="true" />
        <p className="tryon-pane__label">{label}</p>
        <p className="tryon-pane__note">左边的真实拼贴已经可以看了</p>
      </div>
    );
  }

  // 降级 / 失败：展示真实拼贴，并明确说明试穿没有生成。
  if (tryOn.status === "degraded" || tryOn.status === "error" || !tryOn.imageUrl) {
    return (
      <div className="tryon-pane tryon-pane--degraded">
        {collage.imageUrl ? (
          <img src={collage.imageUrl} alt="降级展示的真实单品拼贴" />
        ) : null}
        <div className="tryon-pane__degraded-body">
          <span className="tryon-pane__badge tryon-pane__badge--warn">{label}</span>
          <p className="tryon-pane__note">{tryOn.notice ?? "试穿这次没有生成"}</p>
        </div>
      </div>
    );
  }

  const isUserPhoto = tryOn.subject === "user_reference";

  return (
    <div className="tryon-pane">
      <img
        src={tryOn.imageUrl}
        alt={isUserPhoto ? "AI 生成的真人上身效果" : "固定模特参考图，非本人"}
        style={{ filter: revealed ? "none" : "blur(11px) saturate(1.1)" }}
      />
      {revealed ? (
        <span
          className={`tryon-pane__badge ${
            isUserPhoto ? "tryon-pane__badge--user" : "tryon-pane__badge--model"
          }`}
        >
          {label}
        </span>
      ) : null}
      <button type="button" className="tryon-pane__toggle" onClick={onToggleReveal}>
        {revealed ? "收起试穿" : "👤 显示真人试穿"}
      </button>
      {revealed && tryOn.notice ? (
        <span className="tryon-pane__provenance">{tryOn.notice}</span>
      ) : null}
    </div>
  );
}
