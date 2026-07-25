export interface CapturedVideoFrame {
  file: File;
  width: number;
  height: number;
  timestampMs: number;
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

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("当前浏览器无法捕捉视频画面");
  }
  context.drawImage(video, 0, 0, width, height);

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((result) => {
      if (result) {
        resolve(result);
      } else {
        reject(new Error("当前画面捕捉失败"));
      }
    }, "image/png");
  });
  const timestampMs = Math.max(0, Math.round(video.currentTime * 1_000));
  const safeVideoId = videoId.replaceAll(/[^A-Za-z0-9._-]/g, "-");
  return {
    file: new File([blob], `${safeVideoId}-${timestampMs}.png`, {
      type: "image/png",
      lastModified: Date.now()
    }),
    width,
    height,
    timestampMs
  };
}
