import { describe, expect, it } from "vitest";

import {
  pixelCardColorway,
  pixelCardFallbackBackground
} from "../src/features/wardrobe/pixelCardPalette";

describe("pixel item fallback colorways", () => {
  it("keeps each Item stable while varying backgrounds across the wardrobe", () => {
    const seeds = ["item-a", "item-b", "item-c", "item-d", "item-e", "item-f"];
    const colorways = seeds.map((seed) => pixelCardColorway(seed));

    expect(pixelCardColorway("item-a")).toEqual(pixelCardColorway("item-a"));
    expect(new Set(colorways.map(({ outer }) => outer)).size).toBeGreaterThan(2);
    for (const { outer } of colorways) {
      const channels = outer.match(/[0-9a-f]{2}/gi)?.map((value) => Number.parseInt(value, 16));
      expect(new Set(channels).size).toBeGreaterThan(1);
    }
    expect(pixelCardFallbackBackground("item-a")).toContain("radial-gradient");
  });
});
