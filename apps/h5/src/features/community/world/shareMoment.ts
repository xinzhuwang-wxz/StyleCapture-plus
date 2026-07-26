/**
 * Turns the runway freeze-frame into something worth sending to a friend.
 *
 * The share unit is deliberately the group shot, not a solo portrait: the
 * player's Look surrounded by the guests who reacted to it, with the night's
 * theme on the card. A still is always produced; the animated version is a
 * short loop of the same moment.
 */

import { applyPalette, GIFEncoder, quantize } from "gifenc";

export type ShareSubject = {
  theme: string;
  eyebrow: string;
  /** The player's Look title. */
  lookTitle: string;
  /** Guests visible in the shot, named for the caption. */
  withNames: readonly string[];
  /** Style tags describing the outfit. */
  tags: readonly string[];
  /** Provenance line; never claims a live community. */
  disclaimer: string;
};

export const CARD_WIDTH = 720;
export const CARD_HEIGHT = 1080;
const SCENE_HEIGHT = 720;

function roundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
) {
  context.beginPath();
  context.roundRect(x, y, width, height, radius);
}

/** Paints the card frame around an already-rendered scene image. */
export function drawShareCard(
  canvas: HTMLCanvasElement,
  scene: CanvasImageSource,
  subject: ShareSubject
) {
  const context = canvas.getContext("2d");
  if (!context) throw new Error("浏览器不支持分享卡绘制");

  canvas.width = CARD_WIDTH;
  canvas.height = CARD_HEIGHT;

  context.fillStyle = "#1d1030";
  context.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);

  context.save();
  roundedRect(context, 24, 24, CARD_WIDTH - 48, SCENE_HEIGHT, 22);
  context.clip();
  context.drawImage(scene, 24, 24, CARD_WIDTH - 48, SCENE_HEIGHT);
  context.restore();

  context.strokeStyle = "#f0cf86";
  context.lineWidth = 3;
  roundedRect(context, 24, 24, CARD_WIDTH - 48, SCENE_HEIGHT, 22);
  context.stroke();

  const textTop = SCENE_HEIGHT + 72;
  context.textAlign = "left";
  context.fillStyle = "#f2a8c8";
  context.font = "600 22px 'PingFang SC', sans-serif";
  context.fillText(subject.eyebrow, 44, textTop);

  context.fillStyle = "#fff";
  context.font = "700 46px 'PingFang SC', sans-serif";
  context.fillText(subject.theme, 44, textTop + 54);

  context.fillStyle = "#e8d9f5";
  context.font = "26px 'PingFang SC', sans-serif";
  context.fillText(subject.lookTitle, 44, textTop + 96);

  if (subject.withNames.length) {
    context.fillStyle = "#bfa8d8";
    context.font = "22px 'PingFang SC', sans-serif";
    context.fillText(`同框：${subject.withNames.join("、")}`, 44, textTop + 132);
  }

  let chipX = 44;
  const chipY = textTop + 158;
  context.font = "20px 'PingFang SC', sans-serif";
  subject.tags.forEach((tag) => {
    const width = context.measureText(tag).width + 28;
    if (chipX + width > CARD_WIDTH - 44) return;
    context.fillStyle = "rgba(242, 168, 200, 0.18)";
    roundedRect(context, chipX, chipY, width, 34, 17);
    context.fill();
    context.fillStyle = "#f6cfe2";
    context.fillText(tag, chipX + 14, chipY + 23);
    chipX += width + 10;
  });

  context.fillStyle = "#8e7fa8";
  context.font = "18px 'PingFang SC', sans-serif";
  context.fillText(subject.disclaimer, 44, CARD_HEIGHT - 34);
}

export type GifFrameSource = (index: number) => CanvasImageSource | null;

export type GifOptions = {
  frames: number;
  /** Milliseconds per frame. */
  delay: number;
  width: number;
  height: number;
};

/**
 * Encodes captured scene frames into a looping GIF.
 *
 * A GIF rather than WebM because it is the format that survives being pasted
 * into a chat app, which is the whole point of the share.
 */
export function encodeGif(
  sources: readonly CanvasImageSource[],
  options: GifOptions
): Blob {
  if (!sources.length) throw new Error("没有可用的画面帧");

  const canvas = document.createElement("canvas");
  canvas.width = options.width;
  canvas.height = options.height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("浏览器不支持动图导出");

  const encoder = GIFEncoder();
  let palette: number[][] | null = null;

  sources.forEach((source) => {
    context.clearRect(0, 0, options.width, options.height);
    context.drawImage(source, 0, 0, options.width, options.height);
    const { data } = context.getImageData(0, 0, options.width, options.height);
    // One palette for the whole loop keeps the file small and avoids flicker.
    if (!palette) palette = quantize(data, 256);
    const indexed = applyPalette(data, palette);
    encoder.writeFrame(indexed, options.width, options.height, {
      palette: palette ?? undefined,
      delay: options.delay
    });
  });

  encoder.finish();
  return new Blob([encoder.bytesView()], { type: "image/gif" });
}

export const SCENE_RECT = {
  x: 24,
  y: 24,
  width: CARD_WIDTH - 48,
  height: SCENE_HEIGHT
};

/**
 * Encodes a share card whose caption holds still while the scene inside the
 * frame moves.
 *
 * GIF frames cannot be offset with this encoder, so every frame is card-sized.
 * Instead, everything outside the scene rectangle is written as the transparent
 * index with `dispose: 1` (leave the previous frame in place). Those regions
 * become one long run of a single index, which costs almost nothing once
 * compressed, so the file stays close to the size of the moving part alone.
 */
export function encodeAnimatedCard(
  cards: readonly CanvasImageSource[],
  options: { delay: number; scale?: number }
): Blob {
  if (!cards.length) throw new Error("没有可用的画面帧");

  const scale = options.scale ?? 0.6;
  const width = Math.round(CARD_WIDTH * scale);
  const height = Math.round(CARD_HEIGHT * scale);
  const scene = {
    x: Math.floor(SCENE_RECT.x * scale),
    y: Math.floor(SCENE_RECT.y * scale),
    width: Math.ceil(SCENE_RECT.width * scale),
    height: Math.ceil(SCENE_RECT.height * scale)
  };

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("浏览器不支持动图导出");

  const encoder = GIFEncoder();
  // 255 quantised colours leaves index 255 free to mean "unchanged".
  const transparentIndex = 255;
  let palette: number[][] | null = null;

  cards.forEach((card, frame) => {
    context.clearRect(0, 0, width, height);
    context.drawImage(card, 0, 0, width, height);
    const { data } = context.getImageData(0, 0, width, height);
    if (!palette) palette = quantize(data, transparentIndex);
    const indexed = applyPalette(data, palette);

    if (frame === 0) {
      encoder.writeFrame(indexed, width, height, {
        palette: [...palette, [0, 0, 0]],
        delay: options.delay
      });
      return;
    }

    // Keep only the moving rectangle; the caption is inherited from frame 0.
    for (let y = 0; y < height; y += 1) {
      const insideRow = y >= scene.y && y < scene.y + scene.height;
      for (let x = 0; x < width; x += 1) {
        const inside =
          insideRow && x >= scene.x && x < scene.x + scene.width;
        if (!inside) indexed[y * width + x] = transparentIndex;
      }
    }
    encoder.writeFrame(indexed, width, height, {
      delay: options.delay,
      transparent: true,
      transparentIndex,
      dispose: 1
    });
  });

  encoder.finish();
  return new Blob([encoder.bytesView()], { type: "image/gif" });
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  // Revoking immediately can cancel the download in some browsers.
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
