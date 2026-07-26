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

function isBackdrop(red: number, green: number, blue: number, alpha: number) {
  if (alpha < 20) return true;
  const maximum = Math.max(red, green, blue);
  const minimum = Math.min(red, green, blue);
  return (
    (red > 242 && green > 230 && blue > 230) ||
    (maximum > 232 && maximum - minimum < 30)
  );
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
  for (let index = 0; index < imageData.data.length; index += 4) {
    if (
      isBackdrop(
        imageData.data[index],
        imageData.data[index + 1],
        imageData.data[index + 2],
        imageData.data[index + 3]
      )
    ) {
      imageData.data[index + 3] = 0;
    }
  }
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
