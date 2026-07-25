import { useEffect, useRef } from "react";

import { startPixelSceneLoop } from "./pixelSceneEngine";
import type { PartyStage } from "./communityScene";

const assetRoot = "/assets/community/pixel-agents";
const sceneAssets = {
  floor: `${assetRoot}/floor.png`,
  runway: `${assetRoot}/runway.png`,
  plant: `${assetRoot}/large-plant.png`,
  sofa: `${assetRoot}/sofa.png`,
  painting: `${assetRoot}/painting.png`
} as const;

type LoadedAssets = Partial<Record<keyof typeof sceneAssets, HTMLImageElement>>;

function loadSceneAssets(onReady: (assets: LoadedAssets) => void) {
  const assets: LoadedAssets = {};
  let remaining = Object.keys(sceneAssets).length;
  Object.entries(sceneAssets).forEach(([key, source]) => {
    const image = new Image();
    image.onload = image.onerror = () => {
      assets[key as keyof typeof sceneAssets] = image;
      remaining -= 1;
      if (remaining === 0) onReady(assets);
    };
    image.src = source;
  });
}

function tile(
  context: CanvasRenderingContext2D,
  image: HTMLImageElement | undefined,
  box: { x: number; y: number; width: number; height: number },
  size: number
) {
  if (!image?.naturalWidth) return;
  for (let y = box.y; y < box.y + box.height; y += size) {
    for (let x = box.x; x < box.x + box.width; x += size) {
      context.drawImage(image, x, y, size, size);
    }
  }
}

function drawScene(
  context: CanvasRenderingContext2D,
  assets: LoadedAssets,
  elapsed: number,
  stage: PartyStage
) {
  const width = 360;
  context.fillStyle = "#32244e";
  context.fillRect(0, 0, width, 132);
  tile(context, assets.floor, { x: 0, y: 132, width, height: 298 }, 48);

  context.fillStyle = "rgba(188, 123, 191, .34)";
  context.fillRect(0, 132, width, 298);
  context.fillStyle = "#f4c4d7";
  context.fillRect(96, 118, 168, 312);
  tile(context, assets.runway, { x: 104, y: 126, width: 152, height: 304 }, 76);
  context.fillStyle = "rgba(133, 78, 149, .26)";
  context.fillRect(104, 126, 152, 304);

  context.fillStyle = "#f3d890";
  context.fillRect(16, 20, 328, 4);
  for (let index = 0; index < 8; index += 1) {
    const pulse = Math.sin(elapsed * 4 + index) > 0 ? "#fff2a6" : "#df8fb8";
    context.fillStyle = pulse;
    context.fillRect(24 + index * 44, 16, 8, 8);
  }

  if (assets.painting?.naturalWidth) {
    context.drawImage(assets.painting, 146, 38, 68, 68);
  }
  if (assets.sofa?.naturalWidth) {
    context.drawImage(assets.sofa, 24, 104, 82, 41);
    context.drawImage(assets.sofa, 254, 104, 82, 41);
  }
  if (assets.plant?.naturalWidth) {
    context.drawImage(assets.plant, 12, 120, 72, 108);
    context.drawImage(assets.plant, 276, 120, 72, 108);
  }

  if (stage === "dance") {
    const colors = ["#ff9fc5", "#a8d5ff", "#ffe38d", "#c3a7ff"];
    colors.forEach((color, index) => {
      context.fillStyle = color;
      const x = 116 + ((elapsed * 38 + index * 47) % 128);
      const y = 178 + ((index * 61 + elapsed * 24) % 190);
      context.fillRect(Math.round(x / 6) * 6, Math.round(y / 6) * 6, 6, 6);
    });
  }
}

export function PixelBallroomCanvas({ stage }: { stage: PartyStage }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = 360;
    canvas.height = 430;
    let assets: LoadedAssets = {};
    loadSceneAssets((loaded) => {
      assets = loaded;
    });
    return startPixelSceneLoop(canvas, (context, frame) => {
      drawScene(context, assets, frame.elapsed, stage);
    });
  }, [stage]);

  return (
    <canvas
      ref={canvasRef}
      className="pixel-ballroom__canvas"
      aria-label="使用 Pixel Agents 开源素材构成的像素舞会场景"
    />
  );
}
