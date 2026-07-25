import type { LookRenderSet, RenderArtifact, TryOnArtifact } from "../domain/renderArtifact";

/**
 * 渲染请求里描述一个 Look 的最小输入。
 *
 * Look 只引用 Items，不复制 Item 事实（CONTEXT.md 不变量），所以这里传的是
 * Item 的 id 与图片地址，而不是把 Item 属性再抄一份。
 */
export type LookRenderInput = {
  readonly lookId: string;
  /** 组成这套穿搭的真实单品，顺序即拼贴顺序。 */
  readonly items: ReadonlyArray<{ readonly itemId: string; readonly imageUrl: string }>;
  /**
   * 用户设为「试穿使用」的形象照。没有时后端只能用固定模特，
   * UI 必须相应改标注。
   */
  readonly referencePhotoUrl: string | null;
  /**
   * 人工审核过的演示素材（`curated_seed`）。只有 Feed 种子 Look 有，
   * 用户自由组合出来的 Look 没有。
   *
   * AGENTS.md：`curated_seed` 与真实模型产物是两类不同的来源，
   * 任何时候都不能把前者当成后者展示，所以它单独一个字段而不是混进
   * imageUrl。
   */
  readonly curatedSeed?: {
    readonly modelPhotoUrl: string | null;
    readonly pixelCoverUrl: string | null;
  };
};

/**
 * Issue #5 的统一 RenderArtifact 链。
 *
 * 契约刻意做成「拼贴同步、其余异步」：
 * 「Look 详情先显示由真实 Item 图片生成的拼贴，不等待 GPU 生成。」
 */
export interface RenderPort {
  /**
   * 确定性地生成真实单品拼贴。同一批输入必须得到同一张图，
   * 因此它是同步可等待的，不进任务队列。
   */
  collage(input: LookRenderInput): Promise<RenderArtifact>;

  /**
   * 请求真人试穿。返回首个状态（通常是 processing），
   * 随后通过 `subscribe` 推送 ready / degraded / error。
   */
  requestTryOn(input: LookRenderInput): Promise<TryOnArtifact>;

  /** 请求像素封面，用于衣橱浏览和隐私安全的分享。 */
  requestPixelCover(input: LookRenderInput): Promise<RenderArtifact>;

  /**
   * 订阅一个 Look 的渲染集合。立即回调一次当前状态，
   * 之后每次状态变化再回调。返回取消订阅函数。
   */
  subscribe(input: LookRenderInput, onChange: (set: LookRenderSet) => void): () => void;
}
