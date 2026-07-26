/**
 * Floating pixel reactions — the video-call thumbs-up, drawn as pixel art.
 *
 * Cheering with a single static pose reads as awkward on its own, so applause
 * is expressed by little icons that rise off the crowd and fade, the way
 * reactions behave in a video call.
 *
 * Each icon is a tiny bitmap rather than an emoji glyph, so it matches the
 * world's resolution instead of sitting on top of it as smooth vector art.
 */

export type ReactionKind = "heart" | "thumb" | "balloon" | "confetti";

export type FloatingReaction = {
  /** Spawn position in world units. */
  x: number;
  y: number;
  kind: ReactionKind;
  bornAt: number;
  /** Horizontal drift amplitude; gives each icon its own wobble. */
  drift: number;
  scale: number;
};

export const REACTION_LIFETIME = 1.9;
const RISE = 34;

const BITMAPS: Record<ReactionKind, readonly string[]> = {
  heart: [
    ".##.##.",
    "#######",
    "#######",
    ".#####.",
    "..###..",
    "...#..."
  ],
  thumb: [
    "...##..",
    "..#..#.",
    ".##..#.",
    "######.",
    "#....#.",
    "#....#.",
    "######."
  ],
  balloon: [
    ".###.",
    "#####",
    "#####",
    ".###.",
    "..#..",
    ".#...",
    "..#.."
  ],
  confetti: ["#..#.", "..#..", "#...#", ".#.#.", "#..#."]
};

const PALETTE: Record<ReactionKind, readonly string[]> = {
  heart: ["#ff6b9d", "#ff9ec4"],
  thumb: ["#ffd166", "#ffe9a8"],
  balloon: ["#8ec7ff", "#c3a7ff"],
  confetti: ["#ffe38d", "#ff9ec4", "#a8d5ff", "#c3a7ff"]
};

export const REACTION_KINDS: readonly ReactionKind[] = [
  "heart",
  "thumb",
  "balloon",
  "confetti"
];

/** Progress from 0 at spawn to 1 when the icon has finished fading. */
export function reactionProgress(
  reaction: FloatingReaction,
  now: number
): number {
  return (now - reaction.bornAt) / REACTION_LIFETIME;
}

export function isReactionAlive(
  reaction: FloatingReaction,
  now: number
): boolean {
  return reactionProgress(reaction, now) < 1;
}

/** Current position, rising and wobbling as it goes. */
export function reactionPosition(reaction: FloatingReaction, now: number) {
  const progress = Math.min(1, Math.max(0, reactionProgress(reaction, now)));
  // Ease out so icons leap away from the crowd and then slow down.
  const lift = 1 - (1 - progress) * (1 - progress);
  return {
    x: reaction.x + Math.sin(progress * Math.PI * 2 + reaction.drift * 6) * reaction.drift,
    y: reaction.y - lift * RISE,
    /** Fades over the last 40% of the life. */
    alpha: progress < 0.6 ? 1 : 1 - (progress - 0.6) / 0.4,
    scale: reaction.scale * (0.7 + Math.min(1, progress * 4) * 0.3)
  };
}

export function drawReaction(
  context: CanvasRenderingContext2D,
  reaction: FloatingReaction,
  now: number
) {
  const bitmap = BITMAPS[reaction.kind];
  const colors = PALETTE[reaction.kind];
  const { x, y, alpha, scale } = reactionPosition(reaction, now);
  if (alpha <= 0) return;

  const width = bitmap[0].length;
  const left = x - (width * scale) / 2;
  const top = y - bitmap.length * scale;

  context.save();
  context.globalAlpha = alpha;
  bitmap.forEach((row, rowIndex) => {
    [...row].forEach((cell, columnIndex) => {
      if (cell !== "#") return;
      // Confetti speckles use the whole palette; solid icons shade by row.
      context.fillStyle =
        reaction.kind === "confetti"
          ? colors[(rowIndex + columnIndex) % colors.length]
          : colors[rowIndex < bitmap.length / 2 ? 0 : 1] ?? colors[0];
      context.fillRect(
        left + columnIndex * scale,
        top + rowIndex * scale,
        scale,
        scale
      );
    });
  });
  context.restore();
}
