import type { LookRenderInput, RenderPort } from "../application/renderPort";
import type {
  LookRenderSet,
  RenderArtifact,
  RenderProvenance,
  TryOnArtifact
} from "../domain/renderArtifact";
import { collageInputHash, renderCollage } from "./collageRenderer";

/**
 * Issue #5 后端上线前的渲染适配器。
 *
 * 它刻意不伪造任何生成结果：
 *
 * - 拼贴：真的用用户衣橱里的 Item 图片在 canvas 上合成，是确定性的真实产物。
 * - 试穿：没有接通 try-on provider，所以只有两种诚实结果 —— 有人工审核过的
 *   `curated_seed` 演示素材时按「固定模特参考」展示并标注来源；没有时走
 *   `degraded`，回落到拼贴并说明原因。绝不把降级说成生成成功。
 * - 像素封面：同理，只用 `curated_seed` 素材，缺失时降级到拼贴。
 *
 * 后端 Render API 就位后，替换本文件即可，UI 与领域层不需要改动。
 */

const CURATED_PROVIDER = "curated_seed";
const COLLAGE_PROVIDER = "deterministic-collage";

/** 模拟一次真实往返的排队时间，让 processing 状态在 UI 上真的出现。 */
const TRY_ON_LATENCY_MS = 1_400;
const PIXEL_COVER_LATENCY_MS = 900;

function inputVersionOf(input: LookRenderInput): string {
  return `${input.lookId}@${collageInputHash(input.items.map((item) => item.imageUrl))}`;
}

function provenanceOf(
  input: LookRenderInput,
  capability: string,
  provider: string,
  contentHash: string | null = null
): RenderProvenance {
  return {
    capability,
    provider,
    inputVersion: inputVersionOf(input),
    contentHash
  };
}

function itemImageUrls(input: LookRenderInput): string[] {
  return input.items.map((item) => item.imageUrl);
}

export function createDemoRenderAdapter(): RenderPort {
  /** 缓存只保存真实跑出来过的结果，key 含输入版本，输入变了就不会命中。 */
  const collageCache = new Map<string, RenderArtifact>();

  async function collage(input: LookRenderInput): Promise<RenderArtifact> {
    const urls = itemImageUrls(input);
    const version = inputVersionOf(input);
    const cached = collageCache.get(version);
    if (cached) return cached;

    const contentHash = collageInputHash(urls);
    const imageUrl = await renderCollage(urls);
    const artifact: RenderArtifact = imageUrl
      ? {
          lookId: input.lookId,
          kind: "collage",
          status: "ready",
          imageUrl,
          provenance: provenanceOf(input, "collage", COLLAGE_PROVIDER, contentHash),
          notice: null
        }
      : {
          lookId: input.lookId,
          kind: "collage",
          status: "error",
          imageUrl: null,
          provenance: provenanceOf(input, "collage", COLLAGE_PROVIDER),
          notice: "单品图片没有加载出来，拼贴暂时生成不了"
        };

    if (artifact.status === "ready") collageCache.set(version, artifact);
    return artifact;
  }

  function pendingTryOn(input: LookRenderInput): TryOnArtifact {
    return {
      lookId: input.lookId,
      kind: "try_on",
      status: "processing",
      imageUrl: null,
      subject: input.referencePhotoUrl ? "user_reference" : "fixed_model",
      provenance: provenanceOf(input, "try_on", "unassigned"),
      notice: null
    };
  }

  async function requestTryOn(input: LookRenderInput): Promise<TryOnArtifact> {
    const curated = input.curatedSeed?.modelPhotoUrl ?? null;
    if (curated) {
      return {
        lookId: input.lookId,
        kind: "try_on",
        status: "ready",
        imageUrl: curated,
        // 人工审核过的演示素材不是用户本人，所以只能标固定模特。
        subject: "fixed_model",
        provenance: provenanceOf(input, "try_on", CURATED_PROVIDER),
        notice: "人工审核的演示素材，非本人试穿"
      };
    }

    return {
      lookId: input.lookId,
      kind: "try_on",
      status: "degraded",
      imageUrl: null,
      subject: "collage_fallback",
      provenance: provenanceOf(input, "try_on", "unavailable"),
      notice: "真人试穿服务还没接入，先看真实单品拼贴"
    };
  }

  async function requestPixelCover(input: LookRenderInput): Promise<RenderArtifact> {
    const curated = input.curatedSeed?.pixelCoverUrl ?? null;
    if (curated) {
      return {
        lookId: input.lookId,
        kind: "pixel_cover",
        status: "ready",
        imageUrl: curated,
        provenance: provenanceOf(input, "image_generation", CURATED_PROVIDER),
        notice: null
      };
    }

    return {
      lookId: input.lookId,
      kind: "pixel_cover",
      status: "degraded",
      imageUrl: null,
      provenance: provenanceOf(input, "image_generation", "unavailable"),
      notice: "像素封面还没生成，先用真实拼贴代替"
    };
  }

  function subscribe(
    input: LookRenderInput,
    onChange: (set: LookRenderSet) => void
  ): () => void {
    let cancelled = false;
    const timers: number[] = [];

    let current: LookRenderSet = {
      collage: {
        lookId: input.lookId,
        kind: "collage",
        status: "processing",
        imageUrl: null,
        provenance: provenanceOf(input, "collage", COLLAGE_PROVIDER),
        notice: null
      },
      tryOn: pendingTryOn(input),
      pixelCover: {
        lookId: input.lookId,
        kind: "pixel_cover",
        status: "processing",
        imageUrl: null,
        provenance: provenanceOf(input, "image_generation", "unassigned"),
        notice: null
      }
    };

    const publish = (patch: Partial<LookRenderSet>) => {
      if (cancelled) return;
      current = { ...current, ...patch };
      onChange(current);
    };

    onChange(current);

    // 拼贴不排队：Look 详情必须先看到真实单品。
    void collage(input).then((artifact) => publish({ collage: artifact }));

    timers.push(
      window.setTimeout(() => {
        void requestTryOn(input).then((artifact) => publish({ tryOn: artifact }));
      }, TRY_ON_LATENCY_MS)
    );

    timers.push(
      window.setTimeout(() => {
        void requestPixelCover(input).then((artifact) => publish({ pixelCover: artifact }));
      }, PIXEL_COVER_LATENCY_MS)
    );

    return () => {
      cancelled = true;
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }

  return { collage, requestTryOn, requestPixelCover, subscribe };
}
