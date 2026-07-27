/**
 * Records the share card as a short video.
 *
 * A GIF is the wrong artefact for this: it is large, capped at 256 colours, and
 * most social apps treat it as a second-class attachment. A short H.264 clip is
 * what actually travels — it plays inline, it can be saved to the camera roll,
 * and it is what a phone produces natively.
 *
 * (A true Apple Live Photo is a HEIC still paired with a MOV and cannot be
 * produced from a web page. An MP4 is the closest thing a browser can hand over,
 * and it is the format that shares.)
 */

export type RecordedClip = {
  blob: Blob;
  extension: string;
  mimeType: string;
};

/** Preferred first: H.264 plays everywhere and saves to the camera roll. */
const CANDIDATE_TYPES = [
  "video/mp4;codecs=avc1.42E01E",
  "video/mp4",
  "video/webm;codecs=vp9",
  "video/webm;codecs=vp8",
  "video/webm"
];

export function supportedClipType(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  return (
    CANDIDATE_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null
  );
}

function extensionFor(mimeType: string): string {
  return mimeType.startsWith("video/mp4") ? "mp4" : "webm";
}

export type RecordOptions = {
  /** Total clip length in milliseconds. */
  durationMs: number;
  framesPerSecond: number;
  /**
   * Paints one frame. Called on a timer, so the world keeps moving between
   * calls and the clip shows real motion rather than a still.
   */
  paint: (context: CanvasRenderingContext2D, frame: number) => void;
  width: number;
  height: number;
};

/**
 * Paints frames onto a canvas and records the canvas stream.
 *
 * Dimensions are forced even because H.264 encoders reject odd ones.
 */
export function recordClip(options: RecordOptions): Promise<RecordedClip> {
  const mimeType = supportedClipType();
  if (!mimeType) {
    return Promise.reject(new Error("当前浏览器不支持录制视频"));
  }

  const canvas = document.createElement("canvas");
  canvas.width = options.width - (options.width % 2);
  canvas.height = options.height - (options.height % 2);
  const context = canvas.getContext("2d");
  if (!context) return Promise.reject(new Error("浏览器不支持画面录制"));

  const stream = canvas.captureStream(options.framesPerSecond);
  const recorder = new MediaRecorder(stream, {
    mimeType,
    videoBitsPerSecond: 4_000_000
  });
  const chunks: BlobPart[] = [];
  recorder.ondataavailable = (event) => {
    if (event.data.size) chunks.push(event.data);
  };

  return new Promise<RecordedClip>((resolve, reject) => {
    const totalFrames = Math.max(
      1,
      Math.round((options.durationMs / 1000) * options.framesPerSecond)
    );
    let frame = 0;
    let timer = 0;
    let settled = false;

    const cleanup = () => {
      window.clearInterval(timer);
      stream.getTracks().forEach((track) => track.stop());
    };

    const fail = (error: unknown) => {
      if (settled) return;
      settled = true;
      cleanup();
      if (recorder.state !== "inactive") recorder.stop();
      reject(error instanceof Error ? error : new Error("录制失败"));
    };

    const finish = () => {
      if (settled) return;
      settled = true;
      cleanup();
      const blob = new Blob(chunks, { type: mimeType });
      if (!blob.size) {
        reject(new Error("录制结果为空"));
        return;
      }
      resolve({ blob, extension: extensionFor(mimeType), mimeType });
    };

    recorder.onstop = finish;
    recorder.onerror = () => {
      fail(new Error("录制失败"));
    };

    try {
      // Paint the first frame before starting so the clip never opens on black.
      options.paint(context, 0);
      recorder.start();
      timer = window.setInterval(() => {
        try {
          frame += 1;
          if (frame >= totalFrames) {
            window.clearInterval(timer);
            if (recorder.state !== "inactive") recorder.stop();
            return;
          }
          options.paint(context, frame);
        } catch (error) {
          fail(error);
        }
      }, 1000 / options.framesPerSecond);
    } catch (error) {
      fail(error);
    }
  });
}
