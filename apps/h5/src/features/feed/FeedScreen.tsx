import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import type { CaptureAccepted } from "../../api/client";
import "./feed.css";
import { FeedVideo } from "./FeedVideo";
import { loadFeedManifest } from "./manifest";

export interface FeedScreenProps {
  active?: boolean;
  onAccepted: (accepted: CaptureAccepted, file: File) => void;
  restoreTarget?: {
    videoRef: string;
    timestampMs: number;
    requestId: string;
  } | null;
}

export function FeedScreen({
  active = true,
  onAccepted,
  restoreTarget
}: FeedScreenProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const manifestQuery = useQuery({
    queryKey: ["feed-manifest"],
    queryFn: ({ signal }) => loadFeedManifest(signal),
    staleTime: 5 * 60_000
  });

  useEffect(() => {
    if (!active || !restoreTarget || !manifestQuery.data) return;
    const index = manifestQuery.data.findIndex(
      (asset) => asset.assetId === restoreTarget.videoRef
    );
    if (index < 0) return;
    setActiveIndex(index);
    const container = containerRef.current;
    if (container) {
      container.scrollTo({
        top: index * container.clientHeight,
        behavior: "auto"
      });
    }
  }, [active, manifestQuery.data, restoreTarget]);

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
        <button type="button" onClick={() => void manifestQuery.refetch()}>
          重新加载
        </button>
      </div>
    );
  }

  if (manifestQuery.data.length === 0) {
    return (
      <div className="feed-state feed-state--dark" role="status">
        <span aria-hidden="true">✦</span>
        <strong>暂时没有可播放的穿搭素材</strong>
        <p>素材到位后会自动出现在这里，不会用固定结果冒充真实 Feed。</p>
      </div>
    );
  }

  return (
    <div
      aria-label="穿搭灵感 Feed"
      className="feed-screen"
      data-testid="feed"
      ref={containerRef}
      onScroll={() => {
        const container = containerRef.current;
        if (!container || container.clientHeight <= 0) return;
        const next = Math.round(container.scrollTop / container.clientHeight);
        setActiveIndex(
          Math.max(0, Math.min(next, manifestQuery.data.length - 1))
        );
      }}
    >
      {manifestQuery.data.map((asset, index) => (
        <FeedVideo
          active={active && index === activeIndex}
          asset={asset}
          key={asset.assetId}
          onAccepted={onAccepted}
          restoreRequest={
            restoreTarget && restoreTarget.videoRef === asset.assetId
              ? {
                  requestId: restoreTarget.requestId,
                  timestampMs: restoreTarget.timestampMs
                }
              : null
          }
        />
      ))}
    </div>
  );
}
