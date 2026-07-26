/**
 * Draws a scene map, its props and its inhabitants into one canvas.
 *
 * Everything shares a single world coordinate space and is painted back-to-front
 * by depth, so characters stand in the room instead of floating over a backdrop.
 */

import {
  drawCharacter,
  drawContactShadow,
  type CharacterSprite,
  type RigFrame
} from "./characterRig";
import { drawReaction, type FloatingReaction } from "./reactions";
import {
  mapSize,
  type PropPlacement,
  type SceneMap,
  type TileStyle
} from "./sceneMap";

export type Camera = {
  /** Centre of the view, in world units. */
  x: number;
  y: number;
  /** Destination pixels per world unit. */
  zoom: number;
};

export type Viewport = { width: number; height: number };

export type RenderableCharacter = {
  id: string;
  x: number;
  y: number;
  height: number;
  facing: 1 | -1;
  sprite: CharacterSprite | null;
  frame: RigFrame;
  alpha?: number;
  /** Draws a spotlight pool and glow behind this character. */
  spotlit?: boolean;
  /** Ring drawn at the feet to mark the tapped character. */
  highlighted?: boolean;
  bubble?: { text: string; tone: "speech" | "reaction" } | null;
  nameplate?: string | null;
};

export type PropImages = Partial<Record<string, HTMLImageElement>>;

/** Deterministic per-tile noise, so texture never shimmers between frames. */
function hash(x: number, y: number): number {
  const value = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return value - Math.floor(value);
}

function drawTileFace(
  context: CanvasRenderingContext2D,
  style: TileStyle,
  x: number,
  y: number,
  size: number,
  column: number,
  row: number,
  time: number
) {
  context.fillStyle = style.base;
  context.fillRect(x, y, size, size);
  if (!style.accent) return;
  const half = size / 2;
  const quarter = size / 4;

  switch (style.pattern) {
    case "checker": {
      context.fillStyle = style.accent;
      if ((column + row) % 2 === 0) {
        context.fillRect(x, y, half, half);
        context.fillRect(x + half, y + half, half, half);
      }
      break;
    }
    case "planks": {
      // Long boards running across the room, with staggered end joints.
      context.fillStyle = style.accent;
      context.fillRect(x, y + half - 1, size, 1);
      context.fillRect(x, y + size - 1, size, 1);
      const joint = (row * 5 + column * 3) % 3 === 0 ? quarter : half + quarter;
      context.fillRect(x + joint, y, 1, half);
      break;
    }
    case "carpet": {
      // A runner, not a tiled floor: a lighter centre strip with a woven seam.
      context.fillStyle = style.accent;
      context.fillRect(x + 3, y, size - 6, size);
      context.fillStyle = "rgba(255, 255, 255, 0.10)";
      context.fillRect(x + 3, y + (row % 2 === 0 ? 4 : 11), size - 6, 1);
      break;
    }
    case "grass": {
      context.fillStyle = style.accent;
      for (let blade = 0; blade < 3; blade += 1) {
        const noise = hash(column * 3 + blade, row);
        if (noise > 0.62) {
          const bladeX = x + Math.floor(noise * (size - 2));
          const bladeY = y + Math.floor(hash(row, column + blade) * (size - 3));
          context.fillRect(bladeX, bladeY, 1, 2);
        }
      }
      break;
    }
    case "path": {
      context.fillStyle = style.accent;
      for (let stone = 0; stone < 2; stone += 1) {
        const noise = hash(column + stone * 11, row);
        if (noise > 0.5) {
          context.fillRect(
            x + Math.floor(noise * (size - 4)),
            y + Math.floor(hash(row + stone, column) * (size - 4)),
            3,
            2
          );
        }
      }
      break;
    }
    case "water": {
      context.fillStyle = style.accent;
      const wave = Math.sin(time * 1.6 + column * 0.7 + row * 0.4);
      context.fillRect(x, y + half + wave * 2, size, 1);
      context.fillRect(x + quarter, y + quarter - wave * 1.5, half, 1);
      break;
    }
    case "glass": {
      // Greenhouse panes: mullions plus a diagonal highlight.
      context.fillStyle = style.accent;
      context.fillRect(x, y, 1, size);
      context.fillRect(x, y, size, 1);
      context.globalAlpha = 0.22;
      context.fillRect(x + quarter, y, 2, size);
      context.globalAlpha = 1;
      break;
    }
    case "rug": {
      // Woven field; the border is added by the caller where the rug ends.
      context.fillStyle = style.accent;
      for (let stitch = 0; stitch < 3; stitch += 1) {
        const noise = hash(column * 2 + stitch, row * 3);
        context.fillRect(
          x + Math.floor(noise * (size - 2)),
          y + Math.floor(hash(row * 2 + stitch, column) * (size - 2)),
          2,
          1
        );
      }
      break;
    }
    case "brick": {
      // Staggered courses with mortar lines; the offset row keeps it from
      // reading as a grid of identical boxes.
      context.fillStyle = style.accent;
      context.fillRect(x, y + half - 1, size, 1);
      context.fillRect(x, y + size - 1, size, 1);
      const offset = row % 2 === 0 ? 0 : half;
      context.fillRect(x + ((offset + quarter) % size), y, 1, half);
      context.fillRect(x + ((offset + quarter + half) % size), y + half, 1, half);
      break;
    }
    case "hedge": {
      context.fillStyle = style.accent;
      for (let leaf = 0; leaf < 4; leaf += 1) {
        const noise = hash(column * 5 + leaf, row * 2);
        context.fillRect(
          x + Math.floor(noise * (size - 3)),
          y + Math.floor(hash(row * 5 + leaf, column) * (size - 3)),
          2,
          2
        );
      }
      break;
    }
    default:
      break;
  }
}

function elevationAt(scene: SceneMap, column: number, row: number): number {
  const key = scene.ground[row]?.[column];
  if (!key) return 0;
  return scene.legend[key]?.elevation ?? 0;
}

export function drawGround(
  context: CanvasRenderingContext2D,
  scene: SceneMap,
  camera: Camera,
  viewport: Viewport,
  time: number
) {
  const size = scene.tile;
  const halfWidth = viewport.width / (2 * camera.zoom);
  const halfHeight = viewport.height / (2 * camera.zoom);
  const firstColumn = Math.max(0, Math.floor((camera.x - halfWidth) / size) - 1);
  const lastColumn = Math.ceil((camera.x + halfWidth) / size) + 1;
  const firstRow = Math.max(0, Math.floor((camera.y - halfHeight) / size) - 1);
  const lastRow = Math.min(
    scene.ground.length - 1,
    Math.ceil((camera.y + halfHeight) / size) + 1
  );

  for (let row = firstRow; row <= lastRow; row += 1) {
    const line = scene.ground[row];
    if (!line) continue;
    for (let column = firstColumn; column <= Math.min(lastColumn, line.length - 1); column += 1) {
      const style = scene.legend[line[column]];
      if (!style) continue;
      const x = column * size;
      const y = row * size;
      const elevation = style.elevation ?? 0;

      if (elevation > 0) {
        // Front face first, so the raised top edge overlaps it cleanly.
        if (elevationAt(scene, column, row + 1) === 0) {
          context.fillStyle = style.riser ?? "#000";
          context.fillRect(x, y + size - elevation, size, elevation);
        }
        drawTileFace(context, style, x, y - elevation, size, column, row, time);
        // Gold trim along the exposed rim reads as a stage edge, not a floor seam.
        context.fillStyle = "#f0cf86";
        if (elevationAt(scene, column - 1, row) === 0) {
          context.fillRect(x, y - elevation, 2, size);
        }
        if (elevationAt(scene, column + 1, row) === 0) {
          context.fillRect(x + size - 2, y - elevation, 2, size);
        }
        if (elevationAt(scene, column, row + 1) === 0) {
          context.fillRect(x, y - elevation + size - 2, size, 2);
        }
        if (elevationAt(scene, column, row - 1) === 0) {
          context.fillRect(x, y - elevation, size, 2);
        }
      } else {
        drawTileFace(context, style, x, y, size, column, row, time);
        if (style.pattern === "rug") drawRugEdge(context, scene, column, row);
      }
    }
  }
}

/** Draws a bound edge wherever a rug tile meets something that is not rug. */
function drawRugEdge(
  context: CanvasRenderingContext2D,
  scene: SceneMap,
  column: number,
  row: number
) {
  const size = scene.tile;
  const key = scene.ground[row]?.[column];
  const differs = (otherColumn: number, otherRow: number) =>
    scene.ground[otherRow]?.[otherColumn] !== key;
  const x = column * size;
  const y = row * size;
  context.fillStyle = "rgba(38, 16, 22, 0.42)";
  if (differs(column, row - 1)) context.fillRect(x, y, size, 2);
  if (differs(column, row + 1)) context.fillRect(x, y + size - 2, size, 2);
  if (differs(column - 1, row)) context.fillRect(x, y, 2, size);
  if (differs(column + 1, row)) context.fillRect(x + size - 2, y, 2, size);
}

/** Pulsing lights along the exposed edges of the raised runway. */
export function drawRunwayLights(
  context: CanvasRenderingContext2D,
  scene: SceneMap,
  time: number
) {
  const size = scene.tile;
  context.save();
  for (let row = 0; row < scene.ground.length; row += 1) {
    const line = scene.ground[row];
    if (!line) continue;
    for (let column = 0; column < line.length; column += 1) {
      const elevation = scene.legend[line[column]]?.elevation ?? 0;
      if (elevation === 0) continue;
      const leftEdge = elevationAt(scene, column - 1, row) === 0;
      const rightEdge = elevationAt(scene, column + 1, row) === 0;
      if (!leftEdge && !rightEdge) continue;
      const pulse = 0.55 + 0.45 * Math.sin(time * 3 - row * 0.55);
      context.fillStyle = `rgba(255, 236, 168, ${pulse.toFixed(3)})`;
      const y = row * size - elevation + size / 2 - 1;
      if (leftEdge) context.fillRect(column * size + 1, y, 2, 2);
      if (rightEdge) context.fillRect(column * size + size - 3, y, 2, 2);
    }
  }
  context.restore();
}

function drawProp(
  context: CanvasRenderingContext2D,
  prop: PropPlacement,
  images: PropImages,
  time: number
) {
  const scale = prop.scale ?? 1;
  context.save();
  context.translate(prop.x, prop.y);
  if (prop.flip) context.scale(-1, 1);

  const image = images[prop.kind];
  if (image?.naturalWidth) {
    const sizes: Record<string, { width: number; height: number }> = {
      plant: { width: 36, height: 54 },
      sofa: { width: 46, height: 24 },
      painting: { width: 26, height: 26 }
    };
    const size = sizes[prop.kind] ?? { width: 32, height: 32 };
    const width = size.width * scale;
    const height = size.height * scale;
    context.drawImage(image, -width / 2, -height, width, height);
    context.restore();
    return;
  }

  switch (prop.kind) {
    case "lamp": {
      const glow = 0.6 + 0.4 * Math.sin(time * 2 + prop.x);
      context.fillStyle = "#6b4a86";
      context.fillRect(-2, -26, 4, 26);
      context.fillStyle = "#3c2a54";
      context.fillRect(-5, -2, 10, 3);
      context.fillStyle = `rgba(255, 226, 160, ${(0.35 * glow).toFixed(3)})`;
      context.beginPath();
      context.arc(0, -30, 11, 0, Math.PI * 2);
      context.fill();
      context.fillStyle = "#ffe9b4";
      context.fillRect(-4, -34, 8, 7);
      context.fillStyle = "#fff6dc";
      context.fillRect(-2, -33, 4, 4);
      break;
    }
    case "planter": {
      context.fillStyle = "#8a5f43";
      context.fillRect(-14, -10, 28, 10);
      context.fillStyle = "#a37453";
      context.fillRect(-14, -12, 28, 3);
      context.fillStyle = "#3f7a55";
      for (let leaf = 0; leaf < 7; leaf += 1) {
        context.fillRect(-12 + leaf * 4, -18 - (leaf % 3) * 3, 3, 8);
      }
      const blooms = ["#ff9ec4", "#ffe38d", "#c3a7ff"];
      blooms.forEach((color, index) => {
        context.fillStyle = color;
        context.fillRect(-10 + index * 9, -22 - (index % 2) * 3, 3, 3);
      });
      break;
    }
    case "arch": {
      context.fillStyle = "#5c3f7f";
      context.fillRect(-44, -46, 6, 46);
      context.fillRect(38, -46, 6, 46);
      context.fillRect(-44, -50, 88, 6);
      context.fillStyle = "#3f7a55";
      for (let vine = 0; vine < 11; vine += 1) {
        const drop = 6 + ((vine * 7) % 14);
        context.fillRect(-40 + vine * 8, -44, 2, drop);
      }
      const blooms = ["#ff9ec4", "#ffd9ec", "#ffe38d"];
      for (let bloom = 0; bloom < 9; bloom += 1) {
        context.fillStyle = blooms[bloom % blooms.length];
        context.fillRect(-38 + bloom * 9, -42 + ((bloom * 5) % 12), 3, 3);
      }
      break;
    }
    case "chandelier": {
      const glow = 0.55 + 0.45 * Math.sin(time * 1.5);
      context.fillStyle = "#6b4a86";
      context.fillRect(-1, -40, 2, 22);
      context.fillStyle = "#f3d890";
      context.fillRect(-24, -20, 48, 4);
      for (let bulb = 0; bulb < 5; bulb += 1) {
        const x = -20 + bulb * 10;
        context.fillStyle = `rgba(255, 236, 168, ${(0.3 * glow).toFixed(3)})`;
        context.beginPath();
        context.arc(x, -12, 9, 0, Math.PI * 2);
        context.fill();
        context.fillStyle = "#fff2c4";
        context.fillRect(x - 2, -16, 4, 6);
      }
      break;
    }
    case "counter": {
      // Coffee bar: a wooden top, a panelled front and a couple of mugs.
      context.fillStyle = "#5d3522";
      context.fillRect(-40, -26, 80, 26);
      context.fillStyle = "#8a5a35";
      context.fillRect(-42, -30, 84, 5);
      context.fillStyle = "#4a2c1e";
      for (let panel = 0; panel < 5; panel += 1) {
        context.fillRect(-36 + panel * 16, -22, 2, 18);
      }
      context.fillStyle = "#f4ece0";
      context.fillRect(-26, -36, 6, 6);
      context.fillRect(-14, -35, 5, 5);
      context.fillStyle = "#d8c49f";
      context.fillRect(6, -38, 14, 8);
      break;
    }
    case "banner": {
      // Stage valance hanging over the head of the runway: drapes, scalloped
      // hem and a gold rail, so the walk clearly starts somewhere.
      context.fillStyle = "#8e3660";
      context.fillRect(-52, -30, 104, 18);
      context.fillStyle = "#a84372";
      for (let fold = 0; fold < 13; fold += 1) {
        context.fillRect(-50 + fold * 8, -30, 3, 18);
      }
      context.fillStyle = "#8e3660";
      for (let scallop = 0; scallop < 7; scallop += 1) {
        context.beginPath();
        context.arc(-45 + scallop * 15, -12, 7.5, 0, Math.PI);
        context.fill();
      }
      context.fillStyle = "#f0cf86";
      context.fillRect(-54, -32, 108, 3);
      // Side drapes framing the entrance.
      context.fillStyle = "#7a2c52";
      context.fillRect(-54, -30, 8, 30);
      context.fillRect(46, -30, 8, 30);
      break;
    }
    default:
      break;
  }
  context.restore();
}

function drawBubble(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  text: string,
  tone: "speech" | "reaction",
  bounds: { left: number; right: number }
) {
  context.save();
  context.font = "9px 'PingFang SC', sans-serif";
  context.textBaseline = "middle";
  const paddingX = 6;
  const width = Math.min(120, context.measureText(text).width + paddingX * 2);
  const height = 16;
  // Keep the bubble inside the view; the tail still points at the speaker.
  const left = Math.max(
    bounds.left + 2,
    Math.min(bounds.right - width - 2, x - width / 2)
  );
  const top = y - height;

  // Stardew-style: a warm parchment plate that belongs to the world's palette,
  // with a hard shadow instead of a coloured glow. Reactions differ only by a
  // gold rim, so a room full of bubbles still reads as one material.
  const fill = tone === "reaction" ? "#fff4d8" : "#fdf6ec";
  const ink = tone === "reaction" ? "#6b4326" : "#4a3a52";
  const rim = tone === "reaction" ? "#e0a94b" : "#a08cb0";

  context.fillStyle = "rgba(38, 20, 54, 0.28)";
  context.beginPath();
  context.roundRect(left + 1.5, top + 2, width, height, 5);
  context.fill();

  context.fillStyle = fill;
  context.strokeStyle = rim;
  context.lineWidth = 1;
  context.beginPath();
  context.roundRect(left, top, width, height, 5);
  context.fill();
  context.stroke();

  // Tail pointing down at the speaker.
  const tailX = Math.max(left + 6, Math.min(left + width - 6, x));
  context.beginPath();
  context.moveTo(tailX - 3, top + height - 1);
  context.lineTo(tailX, top + height + 4);
  context.lineTo(tailX + 3, top + height - 1);
  context.closePath();
  context.fillStyle = fill;
  context.fill();
  context.strokeStyle = rim;
  context.stroke();

  context.fillStyle = ink;
  context.textAlign = "center";
  context.fillText(
    text,
    left + width / 2,
    top + height / 2,
    width - paddingX * 2
  );
  context.restore();
}

function drawSpotlight(
  context: CanvasRenderingContext2D,
  character: RenderableCharacter
) {
  const radius = character.height * 0.62;
  const gradient = context.createRadialGradient(
    character.x,
    character.y - character.height * 0.35,
    radius * 0.15,
    character.x,
    character.y - character.height * 0.15,
    radius
  );
  gradient.addColorStop(0, "rgba(255, 240, 200, 0.42)");
  gradient.addColorStop(1, "rgba(255, 240, 200, 0)");
  context.save();
  context.fillStyle = gradient;
  context.beginPath();
  context.ellipse(
    character.x,
    character.y - character.height * 0.2,
    radius,
    radius * 0.85,
    0,
    0,
    Math.PI * 2
  );
  context.fill();
  context.restore();
}

export type WorldRenderInput = {
  scene: SceneMap;
  camera: Camera;
  viewport: Viewport;
  characters: readonly RenderableCharacter[];
  propImages: PropImages;
  time: number;
  /** Pixel applause floating above the crowd. */
  reactions?: readonly FloatingReaction[];
  /** Extra darkening applied outside the spotlight during the runway. */
  vignette?: number;
  devicePixelRatio?: number;
};

export function renderWorld(
  context: CanvasRenderingContext2D,
  input: WorldRenderInput
) {
  const { scene, camera, viewport, characters, propImages, time } = input;
  const ratio = input.devicePixelRatio ?? 1;

  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.fillStyle = scene.backdrop;
  context.fillRect(0, 0, viewport.width, viewport.height);

  context.save();
  context.setTransform(
    camera.zoom * ratio,
    0,
    0,
    camera.zoom * ratio,
    (-camera.x * camera.zoom + viewport.width / 2) * ratio,
    (-camera.y * camera.zoom + viewport.height / 2) * ratio
  );

  // Tiles stay crisp; portraits are illustrations and need filtering.
  context.imageSmoothingEnabled = false;
  drawGround(context, scene, camera, viewport, time);
  drawRunwayLights(context, scene, time);

  const grounded = scene.props.filter((prop) => !prop.overhead);
  const overhead = scene.props.filter((prop) => prop.overhead);

  type Drawable = { depth: number; draw: () => void };
  const drawables: Drawable[] = [];

  grounded.forEach((prop) => {
    drawables.push({
      depth: prop.y,
      draw: () => {
        context.imageSmoothingEnabled = false;
        drawProp(context, prop, propImages, time);
      }
    });
  });

  characters.forEach((character) => {
    drawables.push({
      depth: character.y,
      draw: () => {
        if (character.spotlit) drawSpotlight(context, character);
        context.imageSmoothingEnabled = false;
        drawContactShadow(
          context,
          {
            x: character.x,
            y: character.y,
            height: character.height,
            facing: character.facing,
            alpha: character.alpha
          },
          character.frame
        );
        if (character.highlighted) {
          context.save();
          context.strokeStyle = "rgba(255, 214, 233, 0.95)";
          context.lineWidth = 1.5;
          context.beginPath();
          context.ellipse(
            character.x,
            character.y,
            character.height * 0.3,
            character.height * 0.1,
            0,
            0,
            Math.PI * 2
          );
          context.stroke();
          context.restore();
        }
        if (!character.sprite) return;
        context.imageSmoothingEnabled = true;
        drawCharacter(
          context,
          character.sprite,
          {
            x: character.x,
            y: character.y,
            height: character.height,
            facing: character.facing,
            alpha: character.alpha
          },
          character.frame
        );
      }
    });
  });

  drawables.sort((left, right) => left.depth - right.depth);
  drawables.forEach((drawable) => drawable.draw());

  context.imageSmoothingEnabled = false;
  overhead.forEach((prop) => drawProp(context, prop, propImages, time));

  // Ambient light wash, then bubbles and nameplates above everything.
  const size = mapSize(scene);
  context.fillStyle = scene.ambience;
  context.fillRect(0, 0, size.width, size.height);

  if (input.vignette) {
    // Dim the room around the performer rather than over them, so the person on
    // stage stays the brightest thing in frame.
    const performer = characters.find((character) => character.spotlit);
    const focusX = performer?.x ?? camera.x;
    const focusY = performer ? performer.y - performer.height * 0.45 : camera.y;
    const clear = (performer?.height ?? 60) * 0.95;
    const reach = Math.max(size.width, size.height);
    const falloff = context.createRadialGradient(
      focusX,
      focusY,
      clear,
      focusX,
      focusY,
      clear + reach * 0.35
    );
    falloff.addColorStop(0, "rgba(18, 8, 30, 0)");
    falloff.addColorStop(1, `rgba(18, 8, 30, ${input.vignette})`);
    context.fillStyle = falloff;
    context.fillRect(0, 0, size.width, size.height);
    if (performer) drawSpotlight(context, performer);
  }

  // Applause sits above the crowd but under the speech bubbles.
  input.reactions?.forEach((reaction) =>
    drawReaction(context, reaction, time)
  );

  characters.forEach((character) => {
    if (character.nameplate) {
      context.save();
      context.font = "8px 'PingFang SC', sans-serif";
      context.textAlign = "center";
      context.fillStyle = "rgba(24, 12, 38, 0.72)";
      const width = context.measureText(character.nameplate).width + 8;
      context.fillRect(character.x - width / 2, character.y + 2, width, 11);
      context.fillStyle = "#ffe9f4";
      context.textBaseline = "middle";
      context.fillText(character.nameplate, character.x, character.y + 8);
      context.restore();
    }
    if (character.bubble) {
      drawBubble(
        context,
        character.x,
        character.y - character.height - 6,
        character.bubble.text,
        character.bubble.tone,
        {
          left: camera.x - viewport.width / (2 * camera.zoom),
          right: camera.x + viewport.width / (2 * camera.zoom)
        }
      );
    }
  });

  context.restore();
}
