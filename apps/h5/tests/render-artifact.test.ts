import { describe, expect, it } from "vitest";

import {
  isUserTryOn,
  tryOnLabel,
  type TryOnArtifact
} from "../src/features/render/domain/renderArtifact";
import { createDemoRenderAdapter } from "../src/features/render/infrastructure/demoRenderAdapter";
import { collageInputHash } from "../src/features/render/infrastructure/collageRenderer";
import type { LookRenderInput } from "../src/features/render/application/renderPort";

function tryOn(patch: Partial<TryOnArtifact>): TryOnArtifact {
  return {
    lookId: "look-1",
    kind: "try_on",
    status: "ready",
    imageUrl: "/assets/real-1.jpg",
    subject: "user_reference",
    provenance: {
      capability: "try_on",
      provider: "test",
      inputVersion: "v1",
      contentHash: null
    },
    notice: null,
    ...patch
  };
}

const seededLook: LookRenderInput = {
  lookId: "look-retro-commute",
  items: [
    { itemId: "item-top-1", imageUrl: "/assets/item-top-1.png" },
    { itemId: "item-bottom-1", imageUrl: "/assets/item-bottom-1.png" }
  ],
  referencePhotoUrl: "/assets/real-1.jpg",
  curatedSeed: {
    modelPhotoUrl: "/assets/real-1.jpg",
    pixelCoverUrl: "/assets/pixel-1.png"
  }
};

const customLook: LookRenderInput = {
  lookId: "look-custom-1",
  items: [{ itemId: "item-top-1", imageUrl: "/assets/item-top-1.png" }],
  referencePhotoUrl: "/assets/real-1.jpg"
};

/**
 * Issue #5：「试穿失败、超时或类别不支持时自动降级为拼贴，不能把降级结果标成
 * 真人试穿成功」，且「有用户参考照时才称为用户试穿」。
 */
describe("试穿产物的诚实标注", () => {
  it("只有真实生成且用了用户参考照才叫真人试穿", () => {
    expect(tryOnLabel(tryOn({}))).toBe("✨ AI 真人试穿效果");
    expect(isUserTryOn(tryOn({}))).toBe(true);
  });

  it("没有参考照时必须标注是固定模特", () => {
    const artifact = tryOn({ subject: "fixed_model" });
    expect(tryOnLabel(artifact)).toBe("👗 固定模特参考（非本人）");
    expect(isUserTryOn(artifact)).toBe(false);
  });

  it("降级结果不会被说成生成成功", () => {
    const artifact = tryOn({ status: "degraded", subject: "collage_fallback", imageUrl: null });
    expect(tryOnLabel(artifact)).toBe("🧩 已降级为单品拼贴");
    expect(isUserTryOn(artifact)).toBe(false);
  });

  it("生成中和失败各有自己的说法", () => {
    expect(tryOnLabel(tryOn({ status: "processing", imageUrl: null }))).toBe(
      "⏳ 正在生成真人试穿"
    );
    expect(tryOnLabel(tryOn({ status: "error", imageUrl: null }))).toBe("⚠️ 试穿没有生成");
    expect(isUserTryOn(tryOn({ status: "processing", imageUrl: null }))).toBe(false);
  });
});

describe("Issue #5 上线前的渲染适配器", () => {
  it("有人工审核素材时按固定模特返回，并标明来源", async () => {
    const artifact = await createDemoRenderAdapter().requestTryOn(seededLook);
    expect(artifact.status).toBe("ready");
    // 演示素材不是用户本人，即便用户设了参考照也不能叫真人试穿
    expect(artifact.subject).toBe("fixed_model");
    expect(isUserTryOn(artifact)).toBe(false);
    expect(artifact.provenance.provider).toBe("curated_seed");
    expect(artifact.notice).toContain("非本人");
  });

  it("用户自由组合的 Look 没有试穿素材时如实降级，不伪造结果", async () => {
    const adapter = createDemoRenderAdapter();
    const artifact = await adapter.requestTryOn(customLook);
    expect(artifact.status).toBe("degraded");
    expect(artifact.imageUrl).toBeNull();
    expect(artifact.subject).toBe("collage_fallback");
    expect(artifact.notice).toContain("还没接入");

    const cover = await adapter.requestPixelCover(customLook);
    expect(cover.status).toBe("degraded");
    expect(cover.imageUrl).toBeNull();
  });

  it("产物证据带上输入版本，输入变了版本就变", async () => {
    const adapter = createDemoRenderAdapter();
    const first = await adapter.requestTryOn(seededLook);
    const changed = await adapter.requestTryOn({
      ...seededLook,
      items: [{ itemId: "item-shoe-1", imageUrl: "/assets/item-shoe-1.png" }]
    });
    expect(first.provenance.inputVersion).not.toBe(changed.provenance.inputVersion);
  });
});

describe("拼贴的内容哈希", () => {
  it("同一组单品图得到同一个哈希", () => {
    const urls = ["/assets/item-top-1.png", "/assets/item-bottom-1.png"];
    expect(collageInputHash(urls)).toBe(collageInputHash([...urls]));
  });

  it("换了单品或顺序，哈希就不同 —— 缓存不会命中旧结果", () => {
    const base = ["/assets/item-top-1.png", "/assets/item-bottom-1.png"];
    expect(collageInputHash(base)).not.toBe(collageInputHash([...base].reverse()));
    expect(collageInputHash(base)).not.toBe(
      collageInputHash(["/assets/item-top-1.png", "/assets/item-shoe-1.png"])
    );
  });
});
