import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import type { CaptureAccepted, FeedFrameContext } from "../../api/client";
import {
  FeedSelectionOverlay,
  type FeedSelectionDecision
} from "./FeedSelectionOverlay";
import { FeedCaptureCard, type CaptureCardState } from "./FeedCaptureCard";
import { captureVideoFrame, type CapturedVideoFrame } from "./frameCapture";
import { type FeedAsset, feedMediaUrl } from "./manifest";

interface FeedApi {
  ingestFeedFrame(
    file: File,
    context: FeedFrameContext,
    idempotencyKey: string
  ): Promise<CaptureAccepted>;
}

interface FeedVideoProps {
  active: boolean;
  asset: FeedAsset;
  api: FeedApi;
  onAccepted: (accepted: CaptureAccepted, file: File) => void;
  onEnterMini: () => void;
  onViewAI: (tagLabel: string) => void;
}

type FrameState = CapturedVideoFrame & {
  previewUrl: string;
};

/** 圈选 / 标签 产生的待保存内容 */
type PendingCapture = {
  tagLabel: string;
  context: FeedFrameContext;
  showAIEntry: boolean;
};

/** 暂停后冒出的标签（Tag 交互） */
const FEED_TAGS = [
  { key: "整套穿搭", label: "存整套穿搭", ai: false },
  { key: "同款上衣", label: "存同款上衣", ai: true },
  { key: "同款下装", label: "存同款下装", ai: true },
  { key: "同款鞋子", label: "存同款鞋子", ai: true },
  { key: "同款包包", label: "存同款包包", ai: true }
] as const;

function fullFrameContext(asset: FeedAsset, frame: FrameState, key: string): FeedFrameContext {
  return {
    video_ref: asset.assetId,
    timestamp_ms: frame.timestampMs,
    frame_width: frame.width,
    frame_height: frame.height,
    selections: [
      {
        selection_key: `tag-${key}`,
        polygon: [
          { x: 0.1, y: 0.1 },
          { x: 0.9, y: 0.1 },
          { x: 0.9, y: 0.9 },
          { x: 0.1, y: 0.9 }
        ]
      }
    ]
  };
}

function lassoContext(
  asset: FeedAsset,
  frame: FrameState,
  decision: FeedSelectionDecision
): FeedFrameContext {
  return {
    video_ref: asset.assetId,
    timestamp_ms: frame.timestampMs,
    frame_width: frame.width,
    frame_height: frame.height,
    selections: decision.selections.map((selection) => ({
      selection_key: selection.id,
      polygon: selection.path.map((point) => ({ x: point.x, y: point.y }))
    }))
  };
}

export function FeedVideo({
  active,
  asset,
  api,
  onAccepted,
  onEnterMini,
  onViewAI
}: FeedVideoProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const frameRef = useRef<FrameState | null>(null);
  const mountedRef = useRef(true);
  const reduceMotion = useReducedMotion();

  const [frame, setFrame] = useState<FrameState | null>(null);
  const [pending, setPending] = useState<PendingCapture | null>(null);
  const [cardState, setCardState] = useState<CaptureCardState>("decide");
  const [idempotencyKey, setIdempotencyKey] = useState<string>("");
  const [capturing, setCapturing] = useState(false);
  const [mediaReady, setMediaReady] = useState(false);
  const [mediaError, setMediaError] = useState(false);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const resume = () => {
    const video = videoRef.current;
    if (!video || !active || reduceMotion) return;
    void video.play().catch(() => {});
  };

  const releaseFrame = () => {
    if (frameRef.current) {
      URL.revokeObjectURL(frameRef.current.previewUrl);
      frameRef.current = null;
    }
    setFrame(null);
    setPending(null);
    setCardState("decide");
    setCaptureError(null);
    setSaveError(null);
  };

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (!active || frame || capturing || reduceMotion) {
      video.pause();
      return;
    }
    if (mediaReady) {
      void video.play().catch(() => {});
    }
  }, [active, capturing, frame, mediaReady, reduceMotion]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (frameRef.current) {
        URL.revokeObjectURL(frameRef.current.previewUrl);
        frameRef.current = null;
      }
    };
  }, []);

  const pauseAndCapture = async () => {
    const video = videoRef.current;
    if (!video || !mediaReady || capturing || frame) return;
    video.pause();
    setCapturing(true);
    setCaptureError(null);
    try {
      const captured = await captureVideoFrame(video, asset.assetId);
      const nextFrame = {
        ...captured,
        previewUrl: URL.createObjectURL(captured.file)
      };
      if (!mountedRef.current) {
        URL.revokeObjectURL(nextFrame.previewUrl);
        return;
      }
      frameRef.current = nextFrame;
      setFrame(nextFrame);
    } catch (error) {
      if (!mountedRef.current) return;
      setCaptureError(error instanceof Error ? error.message : "当前画面捕捉失败");
    } finally {
      if (mountedRef.current) setCapturing(false);
    }
  };

  /** 弹出卡片（标签 或 圈选 都汇聚到这里） */
  const openCard = (capture: PendingCapture) => {
    setPending(capture);
    setCardState("decide");
    setSaveError(null);
    setIdempotencyKey(crypto.randomUUID());
  };

  const handleTag = (tag: (typeof FEED_TAGS)[number]) => {
    if (!frame) return;
    openCard({
      tagLabel: tag.key,
      context: fullFrameContext(asset, frame, tag.key),
      showAIEntry: tag.ai
    });
  };

  const handleLassoConfirm = (decision: FeedSelectionDecision) => {
    if (!frame) return;
    openCard({
      tagLabel: decision.selections.length > 1 ? `圈选 ${decision.selections.length} 处` : "圈选穿搭",
      context: lassoContext(asset, frame, decision),
      showAIEntry: true
    });
  };

  /** 右滑 / 点击 → 存入衣橱（走 Mock 或真实 API，由 App 注入） */
  const save = async () => {
    if (!frame || !pending || cardState === "saving") return;
    setCardState("saving");
    setSaveError(null);
    try {
      const accepted = await api.ingestFeedFrame(
        frame.file,
        pending.context,
        idempotencyKey || crypto.randomUUID()
      );
      if (!mountedRef.current) return;
      onAccepted(accepted, frame.file);
      setCardState("saved");
    } catch (error) {
      if (!mountedRef.current) return;
      setSaveError(error instanceof Error ? error.message : "保存失败，请重试");
      setCardState("error");
    }
  };

  const dismiss = () => {
    releaseFrame();
    resume();
  };

  const retryMedia = () => {
    const video = videoRef.current;
    if (!video) return;
    setMediaError(false);
    video.load();
  };

  return (
    <article
      className="feed-video"
      data-active={active ? "true" : "false"}
      aria-label={`${asset.creatorName} 的穿搭`}
    >
      <video
        aria-label={`${asset.creatorName} 的穿搭视频`}
        className="feed-video__media"
        controls={Boolean(reduceMotion)}
        crossOrigin="anonymous"
        loop
        muted
        playsInline
        preload={active ? "auto" : "metadata"}
        ref={videoRef}
        src={feedMediaUrl(asset.localPath)}
        onCanPlay={() => {
          setMediaReady(true);
          setMediaError(false);
        }}
        onClick={reduceMotion ? undefined : () => void pauseAndCapture()}
        onError={() => {
          setMediaReady(false);
          setMediaError(true);
        }}
      />

      <div className="feed-video__shade" aria-hidden="true" />
      <div className="feed-video__meta">
        <strong>@{asset.creatorName}</strong>
        <p>暂停画面，点标签或圈选，把穿搭带进数字衣橱</p>
      </div>

      {/* 右侧操作栏：圈选按钮 */}
      <div className="feed-video__rail">
        <button
          aria-label="暂停并圈选"
          className="feed-video__circle-button"
          disabled={!mediaReady || capturing || Boolean(frame)}
          type="button"
          onClick={() => void pauseAndCapture()}
        >
          <span aria-hidden="true">{capturing ? "…" : "◎"}</span>
          <small>{capturing ? "捕捉中" : "圈选"}</small>
        </button>
      </div>

      {/* 暂停后：标签（Tag）交互 + 圈选层 */}
      {frame && !pending ? (
        <>
          <div className="feed-tags" role="group" aria-label="快速保存标签">
            <p className="feed-tags__title">✦ 存点什么？</p>
            {FEED_TAGS.map((tag) => (
              <button
                key={tag.key}
                type="button"
                className="feed-tag"
                onClick={() => handleTag(tag)}
              >
                {tag.label}
              </button>
            ))}
          </div>
          <FeedSelectionOverlay
            frame={{ videoId: asset.assetId, timestampMs: frame.timestampMs }}
            frameImageUrl={frame.previewUrl}
            videoSize={{ width: frame.width, height: frame.height }}
            onConfirm={handleLassoConfirm}
            onDismiss={dismiss}
          />
        </>
      ) : null}

      {/* 圈选 / 标签 → 弹出卡片（右滑存 / 左滑删） */}
      {frame && pending ? (
        <FeedCaptureCard
          frameImageUrl={frame.previewUrl}
          tagLabel={pending.tagLabel}
          creatorName={asset.creatorName}
          state={cardState}
          errorMessage={saveError}
          showAIEntry={pending.showAIEntry}
          onSave={() => void save()}
          onDismiss={dismiss}
          onViewAI={() => onViewAI(pending.tagLabel)}
          onEnterMini={onEnterMini}
        />
      ) : null}

      {captureError ? (
        <div className="feed-save-error" role="alert">
          <strong>还没抓到这一帧</strong>
          <p>{captureError}</p>
          <div>
            <button type="button" onClick={() => void pauseAndCapture()}>
              再试一次
            </button>
            <button
              type="button"
              onClick={() => {
                setCaptureError(null);
                resume();
              }}
            >
              继续播放
            </button>
          </div>
        </div>
      ) : null}

      {mediaError ? (
        <div className="feed-media-error" role="alert">
          <strong>这条视频暂时没能播放</strong>
          <button type="button" onClick={retryMedia}>
            重新加载
          </button>
        </div>
      ) : null}

      {reduceMotion ? (
        <p className="feed-reduced-motion" role="note">
          已尊重系统的减少动态效果设置，可使用视频控件播放后再圈选。
        </p>
      ) : null}
    </article>
  );
}
