import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import {
  type CaptureAccepted,
  type FeedFrameContext,
  wardrobeApi
} from "../../api/client";
import {
  FeedSelectionOverlay,
  type FeedSelectionDecision
} from "./FeedSelectionOverlay";
import { captureVideoFrame, type CapturedVideoFrame } from "./frameCapture";
import { type FeedAsset, feedMediaUrl } from "./manifest";

interface FeedVideoProps {
  active: boolean;
  asset: FeedAsset;
  onAccepted: (accepted: CaptureAccepted, file: File) => void;
  restoreRequest: {
    requestId: string;
    timestampMs: number;
  } | null;
}

type FrameState = CapturedVideoFrame & {
  previewUrl: string;
};

type SaveAttempt = {
  decision: FeedSelectionDecision;
  idempotencyKey: string;
};

function feedContext(
  asset: FeedAsset,
  frame: FrameState,
  decision: FeedSelectionDecision
): FeedFrameContext {
  return {
    video_ref: asset.assetId,
    timestamp_ms: frame.timestampMs,
    frame_width: frame.width,
    frame_height: frame.height,
    intent: decision.intent,
    selections: decision.selections.map((selection) => ({
      selection_key: selection.id,
      polygon: selection.path.map((point) => ({ x: point.x, y: point.y }))
    }))
  };
}

export function FeedVideo({
  active,
  asset,
  onAccepted,
  restoreRequest
}: FeedVideoProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const frameRef = useRef<FrameState | null>(null);
  const mountedRef = useRef(true);
  const savedTimerRef = useRef<number | null>(null);
  const restoredRequestRef = useRef<string | null>(null);
  const reduceMotion = useReducedMotion();
  const [frame, setFrame] = useState<FrameState | null>(null);
  const [attempt, setAttempt] = useState<SaveAttempt | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [mediaReady, setMediaReady] = useState(false);
  const [mediaError, setMediaError] = useState(false);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [sourceRestored, setSourceRestored] = useState(false);

  const resume = () => {
    const video = videoRef.current;
    if (!video || !active || reduceMotion) {
      return;
    }
    setSourceRestored(false);
    void video.play().catch(() => {
      // Autoplay can be blocked; the visible button remains a user-gesture path.
    });
  };

  const releaseFrame = () => {
    if (frameRef.current) {
      URL.revokeObjectURL(frameRef.current.previewUrl);
      frameRef.current = null;
    }
    setFrame(null);
    setAttempt(null);
    setCaptureError(null);
    setSubmitError(null);
  };

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (
      !active ||
      frame ||
      capturing ||
      submitting ||
      reduceMotion ||
      sourceRestored
    ) {
      video.pause();
      return;
    }
    if (mediaReady) {
      void video.play().catch(() => {
        // The explicit pause/circle button remains available if autoplay is denied.
      });
    }
  }, [
    active,
    capturing,
    frame,
    mediaReady,
    reduceMotion,
    sourceRestored,
    submitting
  ]);

  useEffect(() => {
    const video = videoRef.current;
    if (
      !video ||
      !active ||
      !mediaReady ||
      !restoreRequest ||
      restoredRequestRef.current === restoreRequest.requestId
    ) {
      return;
    }
    restoredRequestRef.current = restoreRequest.requestId;
    video.currentTime = Math.max(0, restoreRequest.timestampMs / 1_000);
    video.pause();
    setSourceRestored(true);
  }, [active, mediaReady, restoreRequest]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (savedTimerRef.current !== null) {
        window.clearTimeout(savedTimerRef.current);
      }
      if (frameRef.current) {
        URL.revokeObjectURL(frameRef.current.previewUrl);
        frameRef.current = null;
      }
    };
  }, []);

  const pauseAndCapture = async () => {
    const video = videoRef.current;
    if (!video || !mediaReady || capturing || submitting || frame) return;
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
      setCaptureError(
        error instanceof Error ? error.message : "当前画面捕捉失败"
      );
    } finally {
      if (mountedRef.current) {
        setCapturing(false);
      }
    }
  };

  const submit = async (nextAttempt: SaveAttempt) => {
    if (!frame || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const accepted = await wardrobeApi.ingestFeedFrame(
        frame.file,
        feedContext(asset, frame, nextAttempt.decision),
        nextAttempt.idempotencyKey
      );
      onAccepted(accepted, frame.file);
      releaseFrame();
      setSaved(true);
      savedTimerRef.current = window.setTimeout(() => setSaved(false), 1_800);
      resume();
    } catch {
      setSubmitError("保存失败，圈选仍保留，可以直接重试");
    } finally {
      setSubmitting(false);
    }
  };

  const confirm = (decision: FeedSelectionDecision) => {
    const nextAttempt = {
      decision,
      idempotencyKey: crypto.randomUUID()
    };
    setAttempt(nextAttempt);
    void submit(nextAttempt);
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
        onClick={
          reduceMotion ? undefined : () => void pauseAndCapture()
        }
        onError={() => {
          setMediaReady(false);
          setMediaError(true);
        }}
      />

      <div className="feed-video__shade" aria-hidden="true" />
      <header className="feed-video__brand" aria-label="StyleCapture Feed">
        <span>STYLECAPTURE</span>
        <strong>灵感 Feed</strong>
      </header>
      <div className="feed-video__meta">
        <strong>@{asset.creatorName}</strong>
        <p>暂停画面，圈住想带进衣橱的单品或整套穿搭</p>
        <a href={asset.sourcePageUrl} target="_blank" rel="noreferrer">
          {asset.sourcePlatform} · {asset.licenseName}
        </a>
      </div>
      <div className="feed-video__rail">
        <button
          aria-label="暂停并圈选"
          className="feed-video__circle-button"
          disabled={!mediaReady || capturing || submitting || Boolean(frame)}
          type="button"
          onClick={() => void pauseAndCapture()}
        >
          <span aria-hidden="true">{capturing ? "…" : "◎"}</span>
          <small>{capturing ? "捕捉中" : "圈选"}</small>
        </button>
      </div>

      {frame && !attempt ? (
        <FeedSelectionOverlay
          frame={{ videoId: asset.assetId, timestampMs: frame.timestampMs }}
          frameImageUrl={frame.previewUrl}
          videoSize={{ width: frame.width, height: frame.height }}
          onConfirm={confirm}
          onDismiss={dismiss}
        />
      ) : null}

      {submitting ? (
        <div className="feed-save-state" role="status">
          <span className="feed-spinner" aria-hidden="true" />
          正在安全存入衣橱…
        </div>
      ) : null}

      {submitError && attempt ? (
        <div
          aria-label="Feed 保存失败"
          className="feed-save-error"
          role="alert"
        >
          <strong>这次还没存进去</strong>
          <p>{submitError}</p>
          <div>
            <button type="button" onClick={() => void submit(attempt)}>
              重试保存
            </button>
            <button type="button" onClick={dismiss}>
              放弃并继续播放
            </button>
          </div>
        </div>
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

      {saved ? (
        <div className="feed-saved-toast" role="status">
          <span aria-hidden="true">✓</span>
          已存入数字衣橱
        </div>
      ) : null}

      {sourceRestored ? (
        <div className="feed-source-restored" role="status">
          已回到收藏时刻 · {Math.round((restoreRequest?.timestampMs ?? 0) / 100) / 10}s
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
