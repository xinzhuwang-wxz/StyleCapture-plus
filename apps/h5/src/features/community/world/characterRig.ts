/**
 * Procedural animation for static full-body portraits.
 *
 * The party has no sprite sheets: every character is a single illustrated
 * portrait, so limb-level animation is impossible. Instead the portrait is drawn
 * as three horizontal bands — head, torso, lower body — each with its own small
 * transform per frame. Bobbing plus a sheared lower band reads as a step, the
 * torso leans against the step, and the head follows a few frames late. That
 * secondary motion is what stops it looking like a swaying sticker.
 *
 * The pose maths is deliberately separate from the drawing so it can be tested
 * without a canvas.
 */

export type RigState = "idle" | "walk" | "pose" | "cheer" | "greet";

export type RigFrame = {
  /** Vertical offset in destination pixels; negative lifts the character. */
  bob: number;
  /** Vertical scale, below 1 when weight lands. */
  squash: number;
  /** Horizontal shear of the lower band, in pixels at the feet. */
  lowerShear: number;
  /** Torso lean in radians, pivoting at the waist. */
  torsoLean: number;
  /** Head sway in destination pixels. */
  headOffset: number;
  /** Head tilt in radians. */
  headTilt: number;
  /** Contact shadow size, 1 when grounded and smaller mid-step. */
  shadowScale: number;
};

/** Band boundaries as fractions of the portrait height. */
export const HEAD_BAND = 0.28;
export const TORSO_BAND = 0.58;

const TAU = Math.PI * 2;
/** The head trails the body by this fraction of a cycle. */
const HEAD_LAG = 0.09;

export function rigFrame(
  state: RigState,
  phase: number,
  height: number
): RigFrame {
  const unit = height / 100;
  const cycle = phase * TAU;

  if (state === "walk") {
    // Two footfalls per cycle, so the bounce runs at double frequency.
    const bounce = Math.abs(Math.sin(cycle));
    const swing = Math.sin(cycle);
    const lagged = Math.sin(cycle - TAU * HEAD_LAG);
    return {
      bob: -bounce * 2.6 * unit,
      squash: 1 - (1 - bounce) * 0.03,
      lowerShear: swing * 4.2 * unit,
      torsoLean: -swing * 0.035,
      headOffset: lagged * 1.1 * unit,
      headTilt: -lagged * 0.04,
      shadowScale: 1 - bounce * 0.22
    };
  }

  if (state === "cheer") {
    const hop = Math.max(0, Math.sin(cycle * 2));
    return {
      bob: -hop * 6 * unit,
      squash: 1 + hop * 0.04,
      lowerShear: Math.sin(cycle) * 1.4 * unit,
      torsoLean: Math.sin(cycle * 2) * 0.05,
      headOffset: Math.sin(cycle * 2 - TAU * HEAD_LAG) * 1.8 * unit,
      headTilt: Math.sin(cycle) * 0.09,
      shadowScale: 1 - hop * 0.4
    };
  }

  if (state === "greet") {
    // A small, friendly rock while the wave artwork is showing.
    const sway = Math.sin(cycle);
    return {
      bob: -Math.abs(sway) * 0.9 * unit,
      squash: 1 + sway * 0.008,
      lowerShear: sway * 0.6 * unit,
      torsoLean: sway * 0.022,
      headOffset: Math.sin(cycle - TAU * HEAD_LAG) * 0.9 * unit,
      headTilt: sway * 0.045,
      shadowScale: 1
    };
  }

  if (state === "pose") {
    const sway = Math.sin(cycle * 0.5);
    return {
      bob: -Math.abs(sway) * 0.5 * unit,
      squash: 1,
      lowerShear: sway * 0.8 * unit,
      torsoLean: sway * 0.018,
      headOffset: sway * 0.6 * unit,
      headTilt: sway * 0.03,
      shadowScale: 1
    };
  }

  // Idle: breathing only, with a slow head drift so standing still stays alive.
  const breath = Math.sin(cycle);
  const drift = Math.sin(cycle * 0.37);
  return {
    bob: -Math.abs(breath) * 0.45 * unit,
    squash: 1 + breath * 0.006,
    lowerShear: 0,
    torsoLean: drift * 0.01,
    headOffset: drift * 0.5 * unit,
    headTilt: drift * 0.022,
    shadowScale: 1
  };
}

/** Walk cycles per second, so faster movement takes quicker steps. */
export function walkCadence(speed: number): number {
  return Math.min(2.6, 0.85 + speed * 0.02);
}

export type CharacterSprite = {
  image: CanvasImageSource;
  width: number;
  height: number;
};

export type CharacterPlacement = {
  /** Feet position in destination pixels. */
  x: number;
  y: number;
  /** Drawn height in destination pixels. */
  height: number;
  facing: 1 | -1;
  /** Extra transparency, used to fade distant or backstage characters. */
  alpha?: number;
};

function drawBand(
  context: CanvasRenderingContext2D,
  sprite: CharacterSprite,
  placement: CharacterPlacement,
  fromFraction: number,
  toFraction: number,
  apply: (context: CanvasRenderingContext2D, bandTop: number) => void
) {
  const width = placement.height * (sprite.width / sprite.height);
  const left = placement.x - width / 2;
  const top = placement.y - placement.height;
  const sourceTop = sprite.height * fromFraction;
  const sourceHeight = sprite.height * (toFraction - fromFraction);
  const bandTop = top + placement.height * fromFraction;
  const bandHeight = placement.height * (toFraction - fromFraction);

  context.save();
  apply(context, bandTop);
  context.drawImage(
    sprite.image,
    0,
    sourceTop,
    sprite.width,
    sourceHeight,
    left,
    bandTop,
    width,
    bandHeight
  );
  context.restore();
}

export function drawContactShadow(
  context: CanvasRenderingContext2D,
  placement: CharacterPlacement,
  frame: RigFrame,
  color = "rgba(38, 18, 52, 0.32)"
) {
  const width = placement.height * 0.3 * frame.shadowScale;
  context.save();
  context.globalAlpha = (placement.alpha ?? 1) * (0.55 + frame.shadowScale * 0.45);
  context.fillStyle = color;
  context.beginPath();
  context.ellipse(
    placement.x,
    placement.y,
    width,
    width * 0.32,
    0,
    0,
    Math.PI * 2
  );
  context.fill();
  context.restore();
}

/**
 * Draws the portrait as three transformed bands.
 *
 * Each band is skewed or rotated about its own top edge so neighbouring bands
 * stay visually joined; drawing them independently around the sprite centre
 * would tear the character apart at the seams.
 */
export function drawCharacter(
  context: CanvasRenderingContext2D,
  sprite: CharacterSprite,
  placement: CharacterPlacement,
  frame: RigFrame
) {
  if (!sprite.width || !sprite.height) return;

  const feetY = placement.y;

  context.save();
  context.globalAlpha = placement.alpha ?? 1;

  // Whole-body transform: bob, landing squash and facing.
  context.translate(placement.x, feetY + frame.bob);
  context.scale(placement.facing, frame.squash);
  context.translate(-placement.x, -feetY);

  // Lower body: sheared about its top edge so the hem swings but the waist holds.
  drawBand(context, sprite, placement, TORSO_BAND, 1, (bandContext, bandTop) => {
    const bandHeight = placement.height * (1 - TORSO_BAND);
    const shear = frame.lowerShear / bandHeight;
    bandContext.translate(0, bandTop);
    bandContext.transform(1, 0, shear, 1, 0, 0);
    bandContext.translate(0, -bandTop);
  });

  // Torso: leans about the waist, countering the step.
  const waistY = placement.y - placement.height * (1 - TORSO_BAND);
  drawBand(
    context,
    sprite,
    placement,
    HEAD_BAND,
    TORSO_BAND,
    (bandContext) => {
      bandContext.translate(placement.x, waistY);
      bandContext.rotate(frame.torsoLean);
      bandContext.translate(-placement.x, -waistY);
    }
  );

  // Head: inherits the torso lean, then adds its own delayed sway.
  const neckY = placement.y - placement.height * (1 - HEAD_BAND);
  drawBand(context, sprite, placement, 0, HEAD_BAND, (bandContext) => {
    bandContext.translate(placement.x, waistY);
    bandContext.rotate(frame.torsoLean);
    bandContext.translate(-placement.x, -waistY);
    bandContext.translate(placement.x + frame.headOffset, neckY);
    bandContext.rotate(frame.headTilt);
    bandContext.translate(-placement.x, -neckY);
  });

  context.restore();
}
