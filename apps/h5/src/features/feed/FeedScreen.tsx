import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import type { CaptureAccepted, FeedFrameContext } from "../../api/client";
import "./feed.css";
import { FeedVideo } from "./FeedVideo";
import { loadFeedManifest } from "./manifest";

interface FeedApi {
  ingestFeedFrame(
    file: File,
    context: FeedFrameContext,
    idempotencyKey: string
  ): Promise<CaptureAccepted>;
}

export interface FeedScreenProps {
  active?: boolean;
  api: FeedApi;
  onAccepted: (accepted: CaptureAccepted, file: File) => void;
  /** 从 Feed 跳转进入小程序 */
  onEnterMini: () => void;
  /** 从单品标签跳转小程序内 AI 搭配 */
  onViewAI: (tagLabel: string) => void;
}

export function FeedScreen({
  active = true,
  api,
  onAccepted,
  onEnterMini,
  onViewAI
}: FeedScreenProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const manifestQuery = useQuery({
    queryKey: ["feed-manifest"],
    queryFn: ({ signal }) => loadFeedManifest(signal),
    staleTime: 5 * 60_000
  });

  if (manifestQuery.isPending) {
    return (
      <div className="feed-state feed-state--dark" role="status">
        <span className="feed-spinner" aria-hidden="true" />
        正在准备穿搭 Feed…
      </div>
    );
  }

  if (manifestQuery.isError) {
    return (
      <div className="feed-state feed-state--dark" role="alert">
        <strong>穿搭 Feed 暂时没有加载出来</strong>
        <p>你的数字衣橱不受影响，可以稍后再试。</p>
        <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
          <button type="button" onClick={() => void manifestQuery.refetch()}>
            重新加载
          </button>
          <button type="button" onClick={onEnterMini}>
            先去小程序
          </button>
        </div>
      </div>
    );
  }

  if (manifestQuery.data.length === 0) {
    return (
      <div className="feed-state feed-state--dark" role="status">
        <span aria-hidden="true">✦</span>
        <strong>暂时没有可播放的穿搭素材</strong>
        <button type="button" onClick={onEnterMini}>
          直接进入小程序
        </button>
      </div>
    );
  }

  return (
    <div className="feed-standalone">
      {/* 顶部品牌 + 小程序入口 */}
      <header className="feed-topbar">
        <div className="feed-topbar__brand" aria-label="码上搭 Feed">
          <span>码上搭</span>
          <strong>穿搭 Feed</strong>
        </div>
        <button
          type="button"
          className="feed-topbar__mini"
          onClick={onEnterMini}
          aria-label="进入码上搭小程序"
        >
          👾 进入小程序 ›
        </button>
      </header>

      <div
        aria-label="穿搭灵感 Feed"
        className="feed-screen"
        data-testid="feed"
        ref={containerRef}
        onScroll={() => {
          const container = containerRef.current;
          if (!container || container.clientHeight <= 0) return;
          const next = Math.round(container.scrollTop / container.clientHeight);
          setActiveIndex(Math.max(0, Math.min(next, manifestQuery.data.length - 1)));
        }}
      >
        {manifestQuery.data.map((asset, index) => (
          <FeedVideo
            active={active && index === activeIndex}
            asset={asset}
            api={api}
            key={asset.assetId}
            onAccepted={onAccepted}
            onEnterMini={onEnterMini}
            onViewAI={onViewAI}
          />
        ))}
      </div>
    </div>
  );
}
