import {
  createCommunityScene,
  moveAvatarTo,
  selectReaction
} from "../src/features/community/communityScene";

describe("pixel dance community scene", () => {
  it("keeps the avatar inside the ballroom and starts dancing on the dance floor", () => {
    const scene = createCommunityScene();

    const dancing = moveAvatarTo(scene, { x: 52, y: 42 });
    const bounded = moveAvatarTo(dancing, { x: 160, y: -20 });

    expect(dancing.avatar).toMatchObject({ x: 52, y: 42, isDancing: true });
    expect(bounded.avatar).toMatchObject({
      x: scene.bounds.maxX,
      y: scene.bounds.minY,
      isDancing: false
    });
  });

  it("shows one of the four approved reactions on the current avatar", () => {
    const scene = createCommunityScene();

    const reacted = selectReaction(scene, "sparkle");

    expect(reacted.avatar.reaction).toBe("sparkle");
    expect(reacted.reactions).toHaveLength(4);
    expect(reacted.residents).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ label: "场景居民", publicTags: expect.any(Array) })
      ])
    );
  });
});
