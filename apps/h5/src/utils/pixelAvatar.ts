/**
 * 像素小人 / 单品图标生成器
 * 用 Canvas 绘制宝可梦式像素风内容，全部确定性生成（同一个 seed 永远长一样），
 * 用于衣橱卡片预览、穿搭卡片、分享卡片与个人形象。
 */

// ─── Hash ──────────────────────────────────────────────

function hashSeed(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i += 1) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** jsdom 等无 Canvas 环境下的 1x1 透明兜底图 */
const FALLBACK_PNG =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";

function safeContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D | null {
  if (
    typeof navigator !== "undefined" &&
    navigator.userAgent.toLowerCase().includes("jsdom")
  ) {
    return null;
  }
  try {
    return canvas.getContext("2d");
  } catch {
    return null;
  }
}

function pick<T>(list: readonly T[], hash: number, salt: number): T {
  return list[(hash + salt * 2654435761) % list.length];
}

// ─── Palettes ──────────────────────────────────────────

const SKIN = ["#ffd9c0", "#ffcfae", "#f7c9a3"] as const;
const HAIR_COLORS = ["#5b3a29", "#3a2a20", "#8a5a3b", "#2b2b3d", "#7a4a56", "#4a3b6b"] as const;
const TOP_COLORS = ["#f9a8d4", "#a78bfa", "#93c5fd", "#fcd34d", "#86efac", "#fda4af", "#e8e4f5"] as const;
const BOTTOM_COLORS = ["#7dd3fc", "#a5b4fc", "#f9a8d4", "#d8d3e8", "#93c5fd", "#c4b5fd"] as const;
const SHOE_COLORS = ["#f472b6", "#a78bfa", "#fbbf24", "#94a3b8"] as const;
const BG_COLORS = ["#f5edfb", "#fdeef5", "#edf4fd", "#fdf6e8", "#eefbef"] as const;

// ─── Pixel Character ───────────────────────────────────
// Grid: 16 x 22. 每个格子是一个像素块。

export interface PixelAvatarOptions {
  /** 输出边长（正方形画布），默认 240 */
  size?: number;
  /** 是否绘制圆形浅色背景，默认 true */
  backdrop?: boolean;
  /** 指定服装配色（不传则由 seed 决定） */
  topColor?: string;
  bottomColor?: string;
  hat?: boolean;
}

const avatarCache = new Map<string, string>();

export function pixelAvatarDataUrl(
  seed: string,
  opts: PixelAvatarOptions = {}
): string {
  const key = `${seed}|${opts.size ?? 240}|${opts.backdrop ?? true}|${opts.topColor ?? ""}|${opts.bottomColor ?? ""}|${opts.hat ? "h" : ""}`;
  const cached = avatarCache.get(key);
  if (cached) return cached;

  const size = opts.size ?? 240;
  const W = 16;
  const H = 22;
  const cell = Math.floor(size / W);
  const canvas = document.createElement("canvas");
  canvas.width = W * cell;
  canvas.height = H * cell;
  const ctx = safeContext(canvas);
  if (!ctx) return FALLBACK_PNG;
  ctx.imageSmoothingEnabled = false;

  const h = hashSeed(seed);
  const skin = pick(SKIN, h, 1);
  const hair = pick(HAIR_COLORS, h, 2);
  const top = opts.topColor ?? pick(TOP_COLORS, h, 3);
  const bottom = opts.bottomColor ?? pick(BOTTOM_COLORS, h, 4);
  const shoes = pick(SHOE_COLORS, h, 5);
  const hairStyle = h % 3; // 0 长发 1 短发 2 双马尾
  const blush = "#ffb3c1";

  const px = (x: number, y: number, w: number, hh: number, color: string) => {
    ctx.fillStyle = color;
    ctx.fillRect(x * cell, y * cell, w * cell, hh * cell);
  };

  // 背景
  if (opts.backdrop !== false) {
    ctx.fillStyle = pick(BG_COLORS, h, 6);
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    // 圆角矩形地砖
    px(3, 19, 10, 1, "rgba(167,139,250,0.25)");
  }

  // ── 头发（后层）──
  if (hairStyle === 0) {
    px(4, 0, 8, 3, hair);
    px(3, 2, 10, 8, hair);
    px(3, 10, 2, 5, hair);
    px(11, 10, 2, 5, hair);
  } else if (hairStyle === 1) {
    px(4, 0, 8, 3, hair);
    px(3, 2, 10, 5, hair);
    px(3, 7, 1, 3, hair);
    px(12, 7, 1, 3, hair);
  } else {
    px(4, 0, 8, 3, hair);
    px(3, 2, 10, 5, hair);
    px(2, 4, 2, 6, hair); // 左马尾
    px(12, 4, 2, 6, hair); // 右马尾
    px(2, 10, 2, 1, "#f9a8d4");
    px(12, 10, 2, 1, "#f9a8d4");
  }

  // ── 脸 ──
  px(4, 3, 8, 6, skin);
  // 刘海
  px(4, 3, 8, 1, hair);
  px(4, 4, 2, 1, hair);
  px(10, 4, 2, 1, hair);
  // 眼睛
  px(5, 6, 2, 2, "#3a2a20");
  px(9, 6, 2, 2, "#3a2a20");
  px(6, 6, 1, 1, "#ffffff"); // 高光
  px(10, 6, 1, 1, "#ffffff");
  // 腮红 + 嘴
  px(4, 8, 1, 1, blush);
  px(11, 8, 1, 1, blush);
  px(7, 8, 2, 1, "#e8798b");

  // ── 帽子（可选）──
  if (opts.hat || h % 4 === 0) {
    px(3, 0, 10, 2, "#f9a8d4");
    px(2, 2, 12, 1, "#f472b6");
    px(7, 0, 2, 1, "#ffffff");
  }

  // ── 身体 ──
  px(6, 9, 4, 1, skin); // 脖子
  px(4, 10, 8, 5, top); // 上衣
  px(3, 10, 1, 4, top); // 左袖
  px(12, 10, 1, 4, top); // 右袖
  px(3, 14, 1, 1, skin); // 左手
  px(12, 14, 1, 1, skin); // 右手
  // 胸前装饰
  px(7, 11, 2, 2, "rgba(255,255,255,0.75)");

  // ── 下装 ──
  const isDress = (h >> 3) % 3 === 0;
  if (isDress) {
    px(4, 15, 8, 3, bottom);
    px(3, 17, 10, 1, bottom);
    px(5, 18, 2, 2, skin);
    px(9, 18, 2, 2, skin);
  } else {
    px(4, 15, 8, 2, bottom);
    px(5, 17, 2, 3, bottom);
    px(9, 17, 2, 3, bottom);
  }

  // ── 鞋子 ──
  px(4, 20, 3, 1, shoes);
  px(9, 20, 3, 1, shoes);
  px(4, 21, 3, 1, "rgba(0,0,0,0.12)");
  px(9, 21, 3, 1, "rgba(0,0,0,0.12)");

  // ── 包包（可选）──
  if ((h >> 5) % 3 === 0) {
    px(13, 13, 2, 2, "#fbbf24");
    px(13, 12, 2, 1, "#b45309");
  }

  const url = canvas.toDataURL("image/png");
  avatarCache.set(key, url);
  return url;
}

// ─── Garment Pixel Icons ───────────────────────────────
// 10x10 像素图：. 空 / M 主色 / D 深色 / W 白

type PixelMap = string[];

const GARMENT_MAPS: Record<string, PixelMap> = {
  帽子: [
    "..........",
    "...MMMM...",
    "..MMMMMM..",
    "..MMMMMM..",
    ".MMMMMMMM.",
    "DDDDDDDDDD",
    "..........",
    "..........",
    "..........",
    ".........."
  ],
  上装: [
    ".MM....MM.",
    "MMMM..MMMM",
    "MMMMMMMMMM",
    "WMMMMMMMMW",
    ".MMMMMMMM.",
    ".MMMMMMMM.",
    ".MMWMMWMM.",
    ".MMMMMMMM.",
    ".MMMMMMMM.",
    ".DDDDDDDD."
  ],
  外套: [
    ".MMM..MMM.",
    "MMMMMMMMMM",
    "MMWMMMMWMM",
    "MMWMMMMWMM",
    "MM.MMMM.MM",
    "MM.MMMM.MM",
    "MM.MMMM.MM",
    "MM.MMMM.MM",
    "MM.MMMM.MM",
    "DD.DDDD.DD"
  ],
  连衣裙: [
    "..MMMMMM..",
    "..MMMMMM..",
    ".WMMMMMMW.",
    "..MMMMMM..",
    "...MMMM...",
    "...MMMM...",
    "..MMMMMM..",
    ".MMMMMMMM.",
    "MMMMMMMMMM",
    "DDDDDDDDDD"
  ],
  下装: [
    "MMMMMMMMMM",
    "MMMMMMMMMM",
    "MMMMMMMMMM",
    "MMMM..MMMM",
    "MMM....MMM",
    "MMM....MMM",
    "MMM....MMM",
    "MMM....MMM",
    "MMM....MMM",
    "DDD....DDD"
  ],
  鞋子: [
    "..........",
    "..........",
    "..MMM.....",
    "..MMMMM...",
    "..MMMMMMM.",
    ".MMMMMMMMM",
    "MMMMMMMMMM",
    "WMMMMMMMMM",
    "DDDDDDDDDD",
    ".........."
  ],
  包包: [
    "...DDDD...",
    "..D....D..",
    ".MMMMMMMM.",
    ".MMMMMMMM.",
    ".MMMMMMMM.",
    ".MMMWWM...",
    ".MMMMMMMM.",
    ".MMMMMMMM.",
    ".DDDDDDDD.",
    ".........."
  ],
  配饰: [
    "..........",
    ".M......M.",
    "..M....M..",
    "...M..M...",
    "....MM....",
    "...MMMM...",
    "..MMMMMM..",
    "...MMMM...",
    "....MM....",
    ".........."
  ]
};

const GARMENT_COLORS: Record<string, [string, string]> = {
  帽子: ["#f9a8d4", "#f472b6"],
  上装: ["#a78bfa", "#8b5cf6"],
  外套: ["#c4b5fd", "#a78bfa"],
  连衣裙: ["#f9a8d4", "#f472b6"],
  下装: ["#93c5fd", "#60a5fa"],
  鞋子: ["#fbbf24", "#f59e0b"],
  包包: ["#fda4af", "#fb7185"],
  配饰: ["#fcd34d", "#f59e0b"]
};

const iconCache = new Map<string, string>();

export function pixelGarmentIcon(
  category: string,
  opts: { size?: number; owned?: boolean; tint?: string } = {}
): string {
  const map = GARMENT_MAPS[category] ?? GARMENT_MAPS["配饰"];
  const key = `${category}|${opts.size ?? 160}|${opts.owned ?? true}|${opts.tint ?? ""}`;
  const cached = iconCache.get(key);
  if (cached) return cached;

  const size = opts.size ?? 160;
  const cell = Math.floor(size / 10);
  const canvas = document.createElement("canvas");
  canvas.width = 10 * cell;
  canvas.height = 10 * cell;
  const ctx = safeContext(canvas);
  if (!ctx) return FALLBACK_PNG;
  ctx.imageSmoothingEnabled = false;

  const [main, dark] = opts.tint
    ? [opts.tint, opts.tint]
    : GARMENT_COLORS[category] ?? ["#c4b5fd", "#a78bfa"];

  map.forEach((row, y) => {
    row.split("").forEach((ch, x) => {
      if (ch === ".") return;
      ctx.fillStyle = ch === "M" ? main : ch === "D" ? dark : "#ffffff";
      ctx.fillRect(x * cell, y * cell, cell, cell);
    });
  });

  if (opts.owned === false) {
    ctx.fillStyle = "rgba(226, 220, 236, 0.55)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  const url = canvas.toDataURL("image/png");
  iconCache.set(key, url);
  return url;
}

// ─── Share Card ────────────────────────────────────────

export function buildShareCard(opts: {
  seed: string;
  title: string;
  subtitle: string;
  badge: "star" | "heart";
}): string {
  const canvas = document.createElement("canvas");
  canvas.width = 480;
  canvas.height = 600;
  const ctx = safeContext(canvas);
  if (!ctx) return FALLBACK_PNG;
  ctx.imageSmoothingEnabled = false;

  // 浅色背景 + 圆角效果由展示层负责
  const grad = ctx.createLinearGradient(0, 0, 480, 600);
  grad.addColorStop(0, "#faf5ff");
  grad.addColorStop(1, "#fdeef5");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 480, 600);

  // 像素点阵装饰
  ctx.fillStyle = "rgba(167,139,250,0.18)";
  for (let i = 0; i < 40; i += 1) {
    const x = (i * 97) % 460;
    const y = (i * 151) % 580;
    ctx.fillRect(x + 8, y + 8, 6, 6);
  }

  // 像素小人
  const avatar = new Image();
  avatar.src = pixelAvatarDataUrl(opts.seed, { size: 300 });
  ctx.drawImage(avatar, 90, 40, 300, 300);

  // 角标
  ctx.font = "44px sans-serif";
  ctx.textAlign = "right";
  ctx.fillText(opts.badge === "star" ? "⭐" : "💖", 452, 76);

  // 文案
  ctx.textAlign = "center";
  ctx.fillStyle = "#3d2c5e";
  ctx.font = "bold 34px 'ZCOOL KuaiLe', 'PingFang SC', sans-serif";
  ctx.fillText(opts.title, 240, 420);
  ctx.fillStyle = "#8b7bb0";
  ctx.font = "22px 'PingFang SC', sans-serif";
  ctx.fillText(opts.subtitle, 240, 462);

  // 底部品牌条
  ctx.fillStyle = "#a78bfa";
  ctx.fillRect(60, 512, 360, 52);
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 24px 'ZCOOL KuaiLe', 'PingFang SC', sans-serif";
  ctx.fillText("👾 码上搭 · 我的数字衣橱", 240, 546);

  return canvas.toDataURL("image/png");
}
