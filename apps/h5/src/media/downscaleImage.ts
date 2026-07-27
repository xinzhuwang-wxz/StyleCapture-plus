/**
 * 把一张照片压成能塞进本机存储的尺寸。
 *
 * 形象照要留在设备上，而 localStorage 通常只有 5MB 上下。一张手机原图动辄
 * 3~6MB，转成 base64 还要再涨三分之一——存两张就满了。所以入库前统一缩到
 * 长边 720、转 JPEG，单张大约 100~200KB，六张仍有余量。
 *
 * 这里只缩放不裁剪：真人试穿参考图要保留完整的身形比例。
 */

export const REFERENCE_MAX_EDGE = 720;
const JPEG_QUALITY = 0.82;

/** 等比缩放后的尺寸；长边不超过 maxEdge，且从不放大。 */
export function fitWithin(
  width: number,
  height: number,
  maxEdge: number
): { width: number; height: number } {
  if (width <= 0 || height <= 0) return { width: 0, height: 0 };
  const longest = Math.max(width, height);
  if (longest <= maxEdge) return { width, height };
  const ratio = maxEdge / longest;
  return {
    width: Math.max(1, Math.round(width * ratio)),
    height: Math.max(1, Math.round(height * ratio))
  };
}

function loadImage(objectUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () =>
      image.naturalWidth > 0
        ? resolve(image)
        : reject(new Error("这张照片读不出来，换一张试试"));
    image.onerror = () => reject(new Error("这张照片读不出来，换一张试试"));
    image.src = objectUrl;
  });
}

/**
 * 读文件 → 等比缩小 → 返回 JPEG data URL。
 *
 * iPhone 的 HEIC 浏览器解不了，会走到 onerror；提示要说清楚是格式问题，而不是
 * 让用户以为照片本身坏了。
 */
export async function downscaleToDataUrl(
  file: File,
  maxEdge: number = REFERENCE_MAX_EDGE
): Promise<string> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = await loadImage(objectUrl);
    const size = fitWithin(image.naturalWidth, image.naturalHeight, maxEdge);
    const canvas = document.createElement("canvas");
    canvas.width = size.width;
    canvas.height = size.height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("这台设备不支持处理照片");
    context.drawImage(image, 0, 0, size.width, size.height);
    const dataUrl = canvas.toDataURL("image/jpeg", JPEG_QUALITY);
    if (!dataUrl.startsWith("data:image/")) {
      throw new Error("照片处理失败，请重试");
    }
    return dataUrl;
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
