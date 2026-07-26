import { describe, expect, it } from "vitest";

import { shouldMountFeedAsset } from "./FeedScreen";

describe("FeedScreen media window", () => {
  it("mounts only the active video and its immediate neighbours", () => {
    const mounted = Array.from({ length: 30 }, (_, index) =>
      shouldMountFeedAsset(index, 10)
    ).filter(Boolean);

    expect(mounted).toHaveLength(3);
    expect(shouldMountFeedAsset(9, 10)).toBe(true);
    expect(shouldMountFeedAsset(10, 10)).toBe(true);
    expect(shouldMountFeedAsset(11, 10)).toBe(true);
    expect(shouldMountFeedAsset(12, 10)).toBe(false);
  });
});
