import { shouldMountFeedAsset } from "../src/features/feed/FeedScreen";

describe("Feed media window", () => {
  it("prepares the first three videos for a smooth cold-start sequence", () => {
    expect(shouldMountFeedAsset(0, 0)).toBe(true);
    expect(shouldMountFeedAsset(1, 0)).toBe(false);
    expect(shouldMountFeedAsset(1, 0, true)).toBe(true);
    expect(shouldMountFeedAsset(2, 0, true)).toBe(true);
    expect(shouldMountFeedAsset(3, 0, true)).toBe(false);
  });

  it("keeps later browsing bounded to the current video and its neighbours", () => {
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
