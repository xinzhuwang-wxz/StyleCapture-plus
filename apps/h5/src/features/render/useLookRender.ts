import { useEffect, useMemo, useState } from "react";

import type { LookRenderInput, RenderPort } from "./application/renderPort";
import type { LookRenderSet } from "./domain/renderArtifact";
import { createDemoRenderAdapter } from "./infrastructure/demoRenderAdapter";

/**
 * 当前生效的 RenderPort 实现。Issue #5 的后端就位后，这里换成 HTTP 适配器，
 * 所有屏幕不需要改。
 */
export const renderPort: RenderPort = createDemoRenderAdapter();

/**
 * 订阅一个 Look 的渲染集合，并在状态推进时重渲染。
 *
 * 返回值永远不为 null：首帧就是 processing，UI 因此总有诚实的状态可显示，
 * 不需要自己造「加载中」的假象。
 */
export function useLookRender(input: LookRenderInput | null): LookRenderSet | null {
  const [renderSet, setRenderSet] = useState<LookRenderSet | null>(null);

  // 订阅只依赖真正影响产物的字段，避免父组件每次渲染都重新排队。
  const signature = useMemo(() => {
    if (!input) return null;
    return JSON.stringify({
      lookId: input.lookId,
      items: input.items.map((item) => item.imageUrl),
      reference: input.referencePhotoUrl,
      curated: input.curatedSeed ?? null
    });
  }, [input]);

  useEffect(() => {
    if (!input || !signature) {
      setRenderSet(null);
      return;
    }
    setRenderSet(null);
    return renderPort.subscribe(input, setRenderSet);
    // input 的身份变化由 signature 代表，故意不把 input 本身列进依赖。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  return renderSet;
}
