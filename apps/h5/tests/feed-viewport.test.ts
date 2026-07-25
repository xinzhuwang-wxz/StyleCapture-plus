import {
  contentBoxForContainedVideo,
  denormalizeVideoPoint,
  normalizePointToVideo
} from "../src/features/feed/viewport";

describe("Feed video viewport mapping adapted from Video Branch", () => {
  it("maps element points through letterboxing into normalized video coordinates", () => {
    const contentBox = contentBoxForContainedVideo(
      { width: 400, height: 800 },
      { width: 1920, height: 1080 }
    );

    expect(contentBox).toEqual({
      x: 0,
      y: 287.5,
      width: 400,
      height: 225
    });
    expect(normalizePointToVideo({ x: 200, y: 400 }, contentBox)).toEqual({
      x: 0.5,
      y: 0.5
    });
    expect(normalizePointToVideo({ x: 200, y: 100 }, contentBox)).toEqual({
      x: 0.5,
      y: 0
    });
  });

  it("maps normalized video points back to element pixels", () => {
    const contentBox = contentBoxForContainedVideo(
      { width: 400, height: 800 },
      { width: 1920, height: 1080 }
    );

    expect(denormalizeVideoPoint({ x: 0.25, y: 0.75 }, contentBox)).toEqual({
      x: 100,
      y: 456.25
    });
  });
});
