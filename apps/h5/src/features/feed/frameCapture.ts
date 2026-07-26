export interface CapturedVideoFrame {
  file: File;
  width: number;
  height: number;
  timestampMs: number;
}

const MAX_CAPTURE_EDGE = 1_440;
const CAPTURE_JPEG_QUALITY = 0.92;
const PRESENTED_FRAME_TIMEOUT_MS = 3_000;

type VideoWithFrameCallbacks = HTMLVideoElement & {
  cancelVideoFrameCallback?: (handle: number) => void;
  requestVideoFrameCallback?: (callback: VideoFrameRequestCallback) => number;
};

function hasDrawableDimensions(video: HTMLVideoElement): boolean {
  return (
    Number.isFinite(video.videoWidth) &&
    Number.isFinite(video.videoHeight) &&
    video.videoWidth > 0 &&
    video.videoHeight > 0
  );
}

function waitForMediaData(
  video: HTMLVideoElement,
  timeoutMs: number
): Promise<void> {
  if (
    video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
    hasDrawableDimensions(video)
  ) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const finish = () => {
      if (!hasDrawableDimensions(video)) return;
      cleanup();
      resolve();
    };
    const fail = () => {
      cleanup();
      reject(new Error("视频画面还没有准备好"));
    };
    const cleanup = () => {
      window.clearTimeout(timer);
      video.removeEventListener("loadeddata", finish);
      video.removeEventListener("canplay", finish);
      video.removeEventListener("error", fail);
    };
    const timer = window.setTimeout(fail, timeoutMs);
    video.addEventListener("loadeddata", finish);
    video.addEventListener("canplay", finish);
    video.addEventListener("error", fail, { once: true });
  });
}

/** Waits until the browser has actually composed a video frame, not only its poster. */
export async function waitForPresentedVideoFrame(
  video: HTMLVideoElement,
  timeoutMs = PRESENTED_FRAME_TIMEOUT_MS
): Promise<void> {
  await waitForMediaData(video, timeoutMs);

  if (video.paused) {
    await video.play();
  }

  const videoWithCallbacks = video as VideoWithFrameCallbacks;
  const requestFrame = videoWithCallbacks.requestVideoFrameCallback;
  if (requestFrame) {
    await new Promise<void>((resolve, reject) => {
      let handle = 0;
      const timer = window.setTimeout(() => {
        videoWithCallbacks.cancelVideoFrameCallback?.(handle);
        reject(new Error("视频首帧仍在加载，请稍候再圈选"));
      }, timeoutMs);
      handle = requestFrame.call(videoWithCallbacks, () => {
        window.clearTimeout(timer);
        resolve();
      });
    });
    return;
  }

  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

export async function captureVideoFrame(
  video: HTMLVideoElement,
  videoId: string
): Promise<CapturedVideoFrame> {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    throw new Error("视频画面还没有准备好");
  }

  const scale = Math.min(1, MAX_CAPTURE_EDGE / Math.max(width, height));
  const outputWidth = Math.max(1, Math.round(width * scale));
  const outputHeight = Math.max(1, Math.round(height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("当前浏览器无法捕捉视频画面");
  }
  context.drawImage(video, 0, 0, outputWidth, outputHeight);

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((result) => {
      if (result) {
        resolve(result);
      } else {
        reject(new Error("当前画面捕捉失败"));
      }
    }, "image/jpeg", CAPTURE_JPEG_QUALITY);
  });
  const timestampMs = Math.max(0, Math.round(video.currentTime * 1_000));
  const safeVideoId = videoId.replaceAll(/[^A-Za-z0-9._-]/g, "-");
  return {
    file: new File([blob], `${safeVideoId}-${timestampMs}.jpg`, {
      type: "image/jpeg",
      lastModified: Date.now()
    }),
    width: outputWidth,
    height: outputHeight,
    timestampMs
  };
}
