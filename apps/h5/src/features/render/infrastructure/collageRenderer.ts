/**
 * 真实单品拼贴渲染器。
 *
 * Issue #5：「Look 详情先显示由真实 Item 图片生成的拼贴，不等待 GPU 生成。」
 * AGENTS.md 允许在没有 GPU 时使用「explicitly labelled deterministic product
 * fallback such as a real-item collage」——这就是那条真实路径：它合成的是用户
 * 衣橱里真实的 Item 图片，不是预先画好的假图。
 *
 * 同一组输入必须产出同一张图，所以这里没有任何随机量：格位由单品数量决定，
 * 顺序由调用方给定。
 */

/** 3:4，与衣橱封面和分享卡同比例。 */
const CANVAS_WIDTH = 900;
const CANVAS_HEIGHT = 1200;

/** 归一化格位：[x, y, w, h]，取值 0–1，乘画布尺寸得到像素。 */
type Slot = readonly [number, number, number, number];

/**
 * 每种单品数量对应一套手工排布，视觉重心与设计稿的拼贴一致：
 * 主件偏左上、配件散落右下，留白均匀。
 */
const LAYOUTS: Record<number, readonly Slot[]> = {
  1: [[0.16, 0.14, 0.68, 0.68]],
  2: [
    [0.06, 0.08, 0.56, 0.42],
    [0.36, 0.52, 0.58, 0.42]
  ],
  3: [
    [0.05, 0.06, 0.52, 0.39],
    [0.58, 0.14, 0.37, 0.28],
    [0.22, 0.50, 0.56, 0.44]
  ],
  4: [
    [0.04, 0.05, 0.48, 0.36],
    [0.56, 0.10, 0.40, 0.30],
    [0.06, 0.46, 0.46, 0.46],
    [0.56, 0.50, 0.40, 0.34]
  ],
  5: [
    [0.03, 0.04, 0.44, 0.33],
    [0.52, 0.06, 0.36, 0.27],
    [0.05, 0.40, 0.42, 0.42],
    [0.52, 0.38, 0.40, 0.30],
    [0.30, 0.76, 0.34, 0.21]
  ],
  6: [
    [0.03, 0.03, 0.40, 0.30],
    [0.48, 0.05, 0.34, 0.25],
    [0.84, 0.10, 0.14, 0.14],
    [0.05, 0.36, 0.40, 0.40],
    [0.50, 0.34, 0.38, 0.29],
    [0.34, 0.78, 0.32, 0.19]
  ]
};

function layoutFor(count: number): readonly Slot[] {
  return LAYOUTS[Math.min(Math.max(count, 1), 6)] ?? LAYOUTS[6];
}

function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = () => resolve(null);
    image.src = src;
  });
}

/** 等比缩放到格位内并居中，避免单品被拉变形。 */
function fitContain(
  image: HTMLImageElement,
  slot: Slot
): { x: number; y: number; width: number; height: number } {
  const boxX = slot[0] * CANVAS_WIDTH;
  const boxY = slot[1] * CANVAS_HEIGHT;
  const boxWidth = slot[2] * CANVAS_WIDTH;
  const boxHeight = slot[3] * CANVAS_HEIGHT;
  const scale = Math.min(boxWidth / image.width, boxHeight / image.height);
  const width = image.width * scale;
  const height = image.height * scale;
  return {
    x: boxX + (boxWidth - width) / 2,
    y: boxY + (boxHeight - height) / 2,
    width,
    height
  };
}

/**
 * 把真实单品图合成为一张 3:4 拼贴，返回 data URL。
 *
 * 加载失败的单品会被跳过而不是画成占位块——拼贴只承诺展示真实存在的图片。
 * 全部加载失败时返回 null，交由调用方按 error 状态处理。
 */
export async function renderCollage(imageUrls: readonly string[]): Promise<string | null> {
  const canvas = document.createElement("canvas");
  canvas.width = CANVAS_WIDTH;
  canvas.height = CANVAS_HEIGHT;
  const context = canvas.getContext("2d");
  if (!context) return null;

  const background = context.createLinearGradient(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
  background.addColorStop(0, "#ffffff");
  background.addColorStop(1, "#faf6ff");
  context.fillStyle = background;
  context.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

  const images = await Promise.all(imageUrls.map(loadImage));
  const drawable = images.filter((image): image is HTMLImageElement => image !== null);
  if (drawable.length === 0) return null;

  const slots = layoutFor(drawable.length);
  drawable.forEach((image, index) => {
    const box = fitContain(image, slots[index % slots.length]);
    context.save();
    context.shadowColor = "rgba(139, 92, 246, 0.16)";
    context.shadowBlur = 24;
    context.shadowOffsetY = 10;
    context.drawImage(image, box.x, box.y, box.width, box.height);
    context.restore();
  });

  return canvas.toDataURL("image/png");
}

/**
 * 内容哈希：同一组单品图必然得到同一个值，用于判断缓存是否命中真实历史结果。
 * 仅用于前端展示与去重，不作为安全用途。
 */
export function collageInputHash(imageUrls: readonly string[]): string {
  const joined = imageUrls.join("|");
  let hash = 2166136261;
  for (let index = 0; index < joined.length; index += 1) {
    hash ^= joined.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}
