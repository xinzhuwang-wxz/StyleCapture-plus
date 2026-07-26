export interface CapturedVideoFrame {
  file: File;
  width: number;
  height: number;
  timestampMs: number;
}

const MAX_CAPTURE_EDGE = 1_440;
const CAPTURE_JPEG_QUALITY = 0.92;

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
