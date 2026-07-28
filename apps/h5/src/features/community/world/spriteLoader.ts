/**
 * Loads character portraits for the world.
 *
 * Bundled Looks are pre-cut by `scripts/pixel_look_cutout.py`, so they load as
 * plain images. A Look the user picks from their own device still arrives as a
 * full illustration card, so it goes through the same backdrop removal at
 * runtime before it can stand in the scene.
 */

import type { CharacterSprite } from "./characterRig";

const cache = new Map<string, Promise<CharacterSprite>>();

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () =>
      image.naturalWidth > 0
        ? resolve(image)
        : reject(new Error("像素 Look 图片不可用"));
    image.onerror = () => reject(new Error("像素 Look 加载失败"));
    image.src = url;
  });
}

/** Keeps the biggest solid shape, dropping card frames and sparkle specks. */
function keepLargestOpaqueShape(imageData: ImageData) {
  const { data, width, height } = imageData;
  const labels = new Int32Array(width * height).fill(-1);
  const queue = new Int32Array(width * height);
  const componentSizes: number[] = [];
  let component = 0;

  for (let index = 0; index < labels.length; index += 1) {
    if (labels[index] !== -1 || data[index * 4 + 3] === 0) continue;
    let start = 0;
    let end = 0;
    let size = 0;
    queue[end++] = index;
    labels[index] = component;
    while (start < end) {
      const current = queue[start++];
      size += 1;
      const x = current % width;
      const y = Math.floor(current / width);
      const neighbors = [
        x > 0 ? current - 1 : -1,
        x < width - 1 ? current + 1 : -1,
        y > 0 ? current - width : -1,
        y < height - 1 ? current + width : -1
      ];
      neighbors.forEach((neighbor) => {
        if (
          neighbor >= 0 &&
          labels[neighbor] === -1 &&
          data[neighbor * 4 + 3] !== 0
        ) {
          labels[neighbor] = component;
          queue[end++] = neighbor;
        }
      });
    }
    componentSizes.push(size);
    component += 1;
  }

  let largest = -1;
  let largestSize = 0;
  componentSizes.forEach((size, index) => {
    if (size > largestSize) {
      largest = index;
      largestSize = size;
    }
  });
  if (largest === -1) return;
  for (let index = 0; index < labels.length; index += 1) {
    if (labels[index] !== largest) data[index * 4 + 3] = 0;
  }
}

const CUTOUT_HEIGHT = 360;


/** 相邻两像素算不算「同一片背景」。 */
const BACKDROP_SPREAD_TOLERANCE = 26;

/**
 * 从画面四边往里漫水，把跟边缘连通的一律清成透明。
 *
 * 原来只按颜色判断（近白、低饱和），可是衣橱的像素封面底是**饱和的粉紫
 * 渐变**：浅的那部分勉强被认出来，深的直接留下，于是人物脚下拖着一块
 * 有色底走进像素世界，跟地图格格不入。
 *
 * 换成从边框漫水之后，背景是什么颜色都无所谓——人物不会碰到卡片边缘，
 * 凡是跟边缘连通的就是背景。容差按「相邻像素之间」比较而不是跟起点比，
 * 所以渐变能一路走下去，而人物边缘的突变会把它挡住。
 */
function clearBackdropFromBorder(imageData: ImageData) {
  const { data, width, height } = imageData;
  const visited = new Uint8Array(width * height);
  const queue = new Int32Array(width * height);
  let head = 0;
  let tail = 0;

  const push = (index: number) => {
    if (visited[index]) return;
    visited[index] = 1;
    queue[tail++] = index;
  };

  for (let x = 0; x < width; x += 1) {
    push(x);
    push((height - 1) * width + x);
  }
  for (let y = 0; y < height; y += 1) {
    push(y * width);
    push(y * width + width - 1);
  }

  while (head < tail) {
    const index = queue[head++];
    const offset = index * 4;
    const red = data[offset];
    const green = data[offset + 1];
    const blue = data[offset + 2];
    data[offset + 3] = 0;

    const x = index % width;
    const y = (index - x) / width;
    const neighbours = [
      x > 0 ? index - 1 : -1,
      x < width - 1 ? index + 1 : -1,
      y > 0 ? index - width : -1,
      y < height - 1 ? index + width : -1
    ];
    for (const neighbour of neighbours) {
      if (neighbour < 0 || visited[neighbour]) continue;
      const next = neighbour * 4;
      if (data[next + 3] < 20) {
        push(neighbour);
        continue;
      }
      const spread =
        Math.abs(data[next] - red) +
        Math.abs(data[next + 1] - green) +
        Math.abs(data[next + 2] - blue);
      if (spread <= BACKDROP_SPREAD_TOLERANCE) push(neighbour);
    }
  }
}

function cutOut(image: HTMLImageElement): CharacterSprite {
  const scale = CUTOUT_HEIGHT / image.naturalHeight;
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = CUTOUT_HEIGHT;
  const context = canvas.getContext("2d");
  if (!context) return { image, width: image.naturalWidth, height: image.naturalHeight };

  context.drawImage(image, 0, 0, width, CUTOUT_HEIGHT);
  const imageData = context.getImageData(0, 0, width, CUTOUT_HEIGHT);
  clearBackdropFromBorder(imageData);
  keepLargestOpaqueShape(imageData);
  context.putImageData(imageData, 0, 0);

  return trim(canvas, context);
}

/** Crops transparent margins so the feet sit at the sprite's bottom edge. */
function trim(
  canvas: HTMLCanvasElement,
  context: CanvasRenderingContext2D
): CharacterSprite {
  const { width, height } = canvas;
  const { data } = context.getImageData(0, 0, width, height);
  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;
  for (let index = 3; index < data.length; index += 4) {
    if (data[index] === 0) continue;
    const pixel = (index - 3) / 4;
    const x = pixel % width;
    const y = Math.floor(pixel / width);
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }
  if (maxX < 0) return { image: canvas, width, height };

  const cropped = document.createElement("canvas");
  cropped.width = maxX - minX + 1;
  cropped.height = maxY - minY + 1;
  const croppedContext = cropped.getContext("2d");
  if (!croppedContext) return { image: canvas, width, height };
  croppedContext.drawImage(
    canvas,
    minX,
    minY,
    cropped.width,
    cropped.height,
    0,
    0,
    cropped.width,
    cropped.height
  );
  return { image: cropped, width: cropped.width, height: cropped.height };
}

/**
 * A character's drawable poses.
 *
 * `idle` is mandatory and is the fallback for every state, so a Look with only
 * one illustration still renders — it just relies on the procedural rig for
 * movement instead of swapping authored art.
 */
export type PoseSet = {
  idle: CharacterSprite;
  walk?: CharacterSprite;
  cheer?: CharacterSprite;
  wave?: CharacterSprite;
};

export const POSE_NAMES = ["idle", "walk", "cheer", "wave"] as const;
export type PoseName = (typeof POSE_NAMES)[number];

export type SpriteRequest = {
  url: string;
  /** Set for user-supplied images that still carry an illustration backdrop. */
  removeBackdrop: boolean;
};

export function loadCharacterSprite(
  request: SpriteRequest
): Promise<CharacterSprite> {
  const key = `${request.removeBackdrop ? "cut" : "raw"}:${request.url}`;
  const existing = cache.get(key);
  if (existing) return existing;

  const pending = loadImage(request.url).then((image) =>
    request.removeBackdrop
      ? cutOut(image)
      : {
          image: image as CanvasImageSource,
          width: image.naturalWidth,
          height: image.naturalHeight
        }
  );
  cache.set(key, pending);
  // A failed load must not poison the cache for a later retry.
  pending.catch(() => cache.delete(key));
  return pending;
}

export function forgetCharacterSprite(url: string) {
  cache.delete(`cut:${url}`);
  cache.delete(`raw:${url}`);
}

/**
 * Loads an authored pose folder such as `/assets/community/poses/cargo`.
 *
 * Only `idle` is required; a missing optional pose degrades to the procedural
 * rig rather than failing the whole character.
 */
export async function loadPoseSet(poseRoot: string): Promise<PoseSet> {
  const idle = await loadCharacterSprite({
    url: `${poseRoot}/idle.png`,
    removeBackdrop: false
  });
  const optional = await Promise.all(
    POSE_NAMES.filter((pose) => pose !== "idle").map(async (pose) => {
      try {
        const sprite = await loadCharacterSprite({
          url: `${poseRoot}/${pose}.png`,
          removeBackdrop: false
        });
        return [pose, sprite] as const;
      } catch {
        return [pose, null] as const;
      }
    })
  );

  const set: PoseSet = { idle };
  optional.forEach(([pose, sprite]) => {
    if (sprite) set[pose as Exclude<PoseName, "idle">] = sprite;
  });
  return set;
}
