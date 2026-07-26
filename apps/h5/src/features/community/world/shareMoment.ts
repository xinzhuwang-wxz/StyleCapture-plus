/**
 * Turns the runway freeze-frame into something worth sending to a friend.
 *
 * The share unit is deliberately the group shot, not a solo portrait: the
 * player's Look surrounded by the guests who reacted to it, with the night's
 * theme on the card. A still is always produced here; the moving version is
 * recorded as a short video by `recordMoment.ts`.
 */

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

export const SCENE_RECT = {
  x: 24,
  y: 24,
  width: CARD_WIDTH - 48,
  height: SCENE_HEIGHT
};

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  // Revoking immediately can cancel the download in some browsers.
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
