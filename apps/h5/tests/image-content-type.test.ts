import { describe, expect, it } from "vitest";

import { detectedContentTypeFor } from "../src/api/client";

describe("mobile gallery image detection", () => {
  it("uses HEIC magic bytes when iOS reports image/jpeg", async () => {
    const bytes = new Uint8Array([
      0, 0, 0, 24,
      0x66, 0x74, 0x79, 0x70,
      0x68, 0x65, 0x69, 0x63,
      0, 0, 0, 0
    ]);
    const file = new File([bytes], "IMG_2310.JPG", { type: "image/jpeg" });

    await expect(detectedContentTypeFor(file)).resolves.toBe("image/heic");
  });

  it("keeps ordinary JPEG gallery bytes as JPEG", async () => {
    const file = new File(
      [new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0])],
      "portrait.jpg",
      { type: "image/jpeg" }
    );

    await expect(detectedContentTypeFor(file)).resolves.toBe("image/jpeg");
  });
});
