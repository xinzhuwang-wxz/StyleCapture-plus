const PIXEL_CARD_COLORWAYS = [
  ["#fff1e9", "#ffd6c4"],
  ["#f6f0ff", "#e2d2ff"],
  ["#edf7ff", "#cfe8ff"],
  ["#ecfaf3", "#cfeedc"],
  ["#fff8e3", "#f7e3a2"],
  ["#fff0f5", "#ffd4e3"]
] as const;

export function pixelCardColorway(seed: string) {
  let hash = 0;
  for (const character of seed) hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  const [outer, glow] = PIXEL_CARD_COLORWAYS[hash % PIXEL_CARD_COLORWAYS.length];
  return { outer, glow };
}

export function pixelCardFallbackBackground(seed: string): string {
  const { outer, glow } = pixelCardColorway(seed);
  return `radial-gradient(circle at 50% 42%, ${glow} 0 38%, transparent 66%), ${outer}`;
}
