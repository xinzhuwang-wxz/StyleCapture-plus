import { useEffect, useImperativeHandle, useRef, type Ref } from "react";

import { startPixelSceneLoop } from "./pixelSceneEngine";
import type { RigState } from "./world/characterRig";
import type { PoseName, PoseSet } from "./world/spriteLoader";
import {
  actorElevation,
  actorHeight,
  actorRigFrame,
  playerOf,
  STAGE_GATHER_RADIUS,
  stepParty,
  walkPlayerTo,
  type PartyWorld
} from "./world/simulation";
import {
  renderWorld,
  type PropImages,
  type RenderableCharacter
} from "./world/worldRenderer";

const propAssetRoot = "/assets/community/pixel-agents";
const propAssets: Record<string, string> = {
  plant: `${propAssetRoot}/large-plant.png`,
  sofa: `${propAssetRoot}/sofa.png`,
  painting: `${propAssetRoot}/painting.png`
};

/**
 * Authored poses cover the discrete states; the procedural rig keeps whichever
 * pose is showing alive between them.
 */
function poseForState(state: RigState): PoseName {
  if (state === "walk") return "walk";
  if (state === "cheer") return "cheer";
  // Saying hello and striking a pose both read best as the wave artwork.
  if (state === "greet" || state === "pose") return "wave";
  return "idle";
}

export type PixelWorldHandle = {
  /** Draws the current frame into an offscreen canvas for export. */
  captureFrame: (width: number, height: number) => HTMLCanvasElement | null;
};

type PixelWorldCanvasProps = {
  world: PartyWorld;
  /** Pose sets keyed by Look id. */
  sprites: Record<string, PoseSet | undefined>;
  onSelectActor?: (actorId: string | null) => void;
  onWalk?: () => void;
  handleRef?: Ref<PixelWorldHandle>;
};

function loadPropImages(onReady: (images: PropImages) => void) {
  const images: PropImages = {};
  const entries = Object.entries(propAssets);
  let remaining = entries.length;
  entries.forEach(([key, source]) => {
    const image = new Image();
    image.onload = image.onerror = () => {
      images[key] = image;
      remaining -= 1;
      if (remaining === 0) onReady({ ...images });
    };
    image.src = source;
  });
}

export function PixelWorldCanvas({
  world,
  sprites,
  onSelectActor,
  onWalk,
  handleRef
}: PixelWorldCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // The loop reads live values without being torn down on every render.
  const worldRef = useRef(world);
  const spritesRef = useRef(sprites);
  const propImagesRef = useRef<PropImages>({});
  const viewportRef = useRef({ width: 360, height: 460 });

  worldRef.current = world;
  spritesRef.current = sprites;

  function buildCharacters(): RenderableCharacter[] {
    const current = worldRef.current;
    return current.actors.map((actor) => {
      const height = actorHeight(current, actor);
      const poses = spritesRef.current[actor.lookId];
      return {
        id: actor.id,
        x: actor.x,
        // Stand on top of raised tiles rather than inside them.
        y: actor.y - actorElevation(current, actor),
        height,
        facing: actor.facing,
        sprite: poses ? (poses[poseForState(actor.state)] ?? poses.idle) : null,
        frame: actorRigFrame(actor, height),
        spotlit:
          actor.kind === "player" &&
          (current.phase === "walking" ||
            current.phase === "posing" ||
            current.phase === "frozen"),
        highlighted: current.selectedActorId === actor.id,
        bubble: actor.bubble
          ? { text: actor.bubble.text, tone: actor.bubble.tone }
          : null,
        nameplate:
          actor.kind === "guest" && current.conversation?.guestId !== actor.id
            ? actor.name
            : null
      };
    });
  }

  useImperativeHandle(handleRef, () => ({
    captureFrame(width: number, height: number) {
      const current = worldRef.current;
      const offscreen = document.createElement("canvas");
      offscreen.width = width;
      offscreen.height = height;
      const context = offscreen.getContext("2d");
      if (!context) return null;
      const player = playerOf(current);
      // Frame wide enough to hold the performer and the guests gathered around
      // them, so a card that names co-stars actually shows them.
      const framedWorldWidth = STAGE_GATHER_RADIUS * 3.4;
      renderWorld(context, {
        scene: current.scene,
        camera: {
          x: player.x,
          y: player.y - 26,
          zoom: width / framedWorldWidth
        },
        viewport: { width, height },
        characters: buildCharacters(),
        propImages: propImagesRef.current,
        time: current.time,
        reactions: current.reactions,
        vignette: current.vignette,
        devicePixelRatio: 1
      });
      return offscreen;
    }
  }));

  useEffect(() => {
    loadPropImages((images) => {
      propImagesRef.current = images;
    });
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) return;
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      viewportRef.current = { width: rect.width, height: rect.height };
      canvas.width = Math.round(rect.width * ratio);
      canvas.height = Math.round(rect.height * ratio);
    };
    resize();
    // A window resize listener misses layout changes the window does not cause
    // — entering and leaving immersive mode only swaps a class, which left the
    // canvas stretched at its previous size. Observing the element itself
    // catches every case.
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    window.addEventListener("resize", resize);

    if (import.meta.env.DEV) {
      // Guests wander, so screenshot scripts need a way to aim at a moving
      // target. Development only; absent from the production bundle.
      (window as unknown as Record<string, unknown>).__styleParty = {
        world: () => worldRef.current,
        viewport: () => viewportRef.current,
        canvas
      };
    }

    const stop = startPixelSceneLoop(canvas, (context, frame) => {
      const current = worldRef.current;
      stepParty(current, frame.delta, viewportRef.current);
      renderWorld(context, {
        scene: current.scene,
        camera: current.camera,
        viewport: viewportRef.current,
        characters: buildCharacters(),
        propImages: propImagesRef.current,
        time: current.time,
        reactions: current.reactions,
        vignette: current.vignette,
        devicePixelRatio: Math.min(2, window.devicePixelRatio || 1)
      });
    });

    return () => {
      stop();
      observer.disconnect();
      window.removeEventListener("resize", resize);
    };
    // The loop is intentionally started once; live state arrives through refs.
  }, []);

  function handlePointer(event: React.PointerEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const current = worldRef.current;
    const rect = canvas.getBoundingClientRect();
    const viewport = viewportRef.current;
    const worldX =
      (event.clientX - rect.left - viewport.width / 2) / current.camera.zoom +
      current.camera.x;
    const worldY =
      (event.clientY - rect.top - viewport.height / 2) / current.camera.zoom +
      current.camera.y;

    // Tapping a guest inspects them; tapping the floor walks there.
    const tapped = current.actors.find((actor) => {
      if (actor.kind !== "guest") return false;
      const height = actorHeight(current, actor);
      return (
        Math.abs(worldX - actor.x) < height * 0.24 &&
        worldY > actor.y - height &&
        worldY < actor.y + 6
      );
    });

    if (tapped) {
      onSelectActor?.(tapped.id);
      // Walk over to them; standing close is what starts the conversation.
      const player = playerOf(current);
      const side = player.x <= tapped.x ? -1 : 1;
      walkPlayerTo(current, tapped.x + side * 22, tapped.y + 4);
      onWalk?.();
      return;
    }
    onSelectActor?.(null);
    if (walkPlayerTo(current, worldX, worldY)) onWalk?.();
  }

  return (
    <canvas
      ref={canvasRef}
      className="pixel-world__canvas"
      onPointerDown={handlePointer}
      aria-label="花房夜宴像素世界，点击地面走动，点击角色查看他的 Look"
    />
  );
}
