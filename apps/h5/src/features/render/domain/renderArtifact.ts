/**
 * RenderArtifact 领域模型（Issue #5）
 *
 * CONTEXT.md：「RenderArtifact 是与准确输入版本和 provider 证据绑定的派生产物
 * ——拼贴、试穿、像素封面或后续动画。」
 *
 * 这一层是纯领域类型，不引用 React、fetch、canvas 或任何 provider 名称。
 * Product API 上线后，只有 infrastructure 适配器需要改。
 */

/** 一个 Look 会派生出的三类产物。 */
export type RenderKind = "collage" | "try_on" | "pixel_cover";

/**
 * ProcessingState 的渲染子集。客户端必须诚实渲染这些状态
 * （CONTEXT.md：「clients must render these honestly」）。
 *
 * - `ready`：产物真实生成成功。
 * - `processing`：任务已受理，还在生成。
 * - `degraded`：试穿失败/超时/类别不支持，已回落到拼贴。
 *   Issue #5：「不能把降级结果标成真人试穿成功」。
 * - `error`：连降级产物都拿不到。
 */
export type RenderStatus = "processing" | "ready" | "degraded" | "error";

/**
 * 试穿图的来源，决定 UI 上允许怎么称呼它。
 *
 * Issue #5：「有用户参考照时才称为用户试穿；没有参考照时使用固定模特或拼贴，
 * 并在 UI 中明确标注。」
 */
export type TryOnSubject =
  /** 用了用户自己的形象照，可以叫「真人试穿」。 */
  | "user_reference"
  /** 没有参考照，用固定模特，必须标注。 */
  | "fixed_model"
  /** 没有试穿结果，展示的是拼贴。 */
  | "collage_fallback";

/**
 * 产物的证据字段。Issue #5 要求 RenderArtifact 记录输入版本、provider、模型、
 * 参数、状态与内容哈希，且「缓存只能命中真实历史结果」。
 *
 * 前端不解释这些值，只负责透传与展示来源，避免把降级说成成功。
 */
export type RenderProvenance = {
  /** 产出这张图的能力别名，例如 `try_on` / `image_generation`。 */
  readonly capability: string;
  /** 供应链标识，例如 `deterministic-collage`、`managed-try-on`。 */
  readonly provider: string;
  /** 生成这张图所依据的 Item 版本集合，用于判断缓存是否仍然有效。 */
  readonly inputVersion: string;
  /** 内容哈希，命中缓存时与历史结果一致。 */
  readonly contentHash: string | null;
};

export type RenderArtifact = {
  readonly lookId: string;
  readonly kind: RenderKind;
  readonly status: RenderStatus;
  /** 可直接渲染的图片地址；processing / error 时为 null。 */
  readonly imageUrl: string | null;
  readonly provenance: RenderProvenance;
  /** 面向用户的状态说明，降级时解释原因。 */
  readonly notice: string | null;
};

/** 试穿产物额外带上「这张图能不能叫真人试穿」。 */
export type TryOnArtifact = RenderArtifact & {
  readonly kind: "try_on";
  readonly subject: TryOnSubject;
};

/** 一个 Look 的完整渲染集合。 */
export type LookRenderSet = {
  readonly collage: RenderArtifact;
  readonly tryOn: TryOnArtifact;
  readonly pixelCover: RenderArtifact;
};

/**
 * 试穿面板的标题文案。集中在领域层，避免各处 UI 各自发挥、
 * 把降级结果说成生成成功。
 */
export function tryOnLabel(artifact: TryOnArtifact): string {
  if (artifact.status === "processing") return "⏳ 正在生成真人试穿";
  if (artifact.status === "error") return "⚠️ 试穿没有生成";
  if (artifact.status === "degraded") return "🧩 已降级为单品拼贴";
  return artifact.subject === "user_reference"
    ? "✨ AI 真人试穿效果"
    : "👗 固定模特参考（非本人）";
}

/** 只有真实生成、且用了用户参考照的结果才算「用户试穿」。 */
export function isUserTryOn(artifact: TryOnArtifact): boolean {
  return artifact.status === "ready" && artifact.subject === "user_reference";
}
