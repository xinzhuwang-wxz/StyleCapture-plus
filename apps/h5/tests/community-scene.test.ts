import {
  MY_LOOK_ID,
  createCommunityScene,
  lookById,
  randomOtherLook,
  reactToSelectedLook,
  replaceMyLook,
  selectPartyLook,
  selectedPartyLook,
  toggleSavedLook,
  wearLook,
  wornLook
} from "../src/features/community/communityScene";

describe("theme party scene", () => {
  it("starts as a truthful curated showcase", () => {
    const scene = createCommunityScene();

    expect(scene.theme).toMatchObject({
      title: "花房夜宴",
      promise: "让每套像素搭配被看见、被收藏、被分享"
    });
    expect(scene.looks.length).toBeGreaterThanOrEqual(4);
    scene.looks.forEach((look) =>
      expect(look).toMatchObject({
        sourceKind: "curated-seed",
        sourceLabel: "精选示例 · 非真人"
      })
    );
    // Each authored pose set is worn by a guest, so the player starts in a Look
    // nobody else is wearing.
    expect(wornLook(scene).poseRoot).toBeUndefined();
    expect(scene.looks.filter((look) => look.poseRoot).length).toBeGreaterThanOrEqual(4);
    expect(lookById(scene, MY_LOOK_ID)).toBeUndefined();
    expect(wornLook(scene).sourceKind).toBe("curated-seed");
  });

  it("wears a supplied public render artifact from the start", () => {
    const scene = createCommunityScene({
      assetUrl: "/assets/my-pixel-look.png",
      label: "我的公开像素 Look",
      kind: "public-render-artifact"
    });

    expect(scene.wornLookId).toBe(MY_LOOK_ID);
    expect(wornLook(scene)).toMatchObject({
      assetUrl: "/assets/my-pixel-look.png",
      sourceKind: "my-look",
      sourceLabel: "我的公开像素 Look"
    });
  });

  it("changes the whole outfit and keeps the detail panel in sync", () => {
    const scene = wearLook(createCommunityScene(), "curated-mint");

    expect(scene.wornLookId).toBe("curated-mint");
    expect(selectedPartyLook(scene).id).toBe("curated-mint");
  });

  it("ignores an unknown Look id instead of clearing the outfit", () => {
    const scene = createCommunityScene();

    expect(wearLook(scene, "missing")).toBe(scene);
    expect(selectPartyLook(scene, "missing")).toBe(scene);
  });

  it("adds a local upload to the wardrobe without dressing the character in it", () => {
    const scene = createCommunityScene();
    const uploaded = replaceMyLook(scene, {
      assetUrl: "blob:my-uploaded-look",
      label: "my-look.png",
      kind: "local-upload"
    });

    expect(uploaded.looks).toHaveLength(scene.looks.length + 1);
    expect(uploaded.selectedLookId).toBe(MY_LOOK_ID);
    // Uploading only previews it; wearing it stays an explicit choice.
    expect(uploaded.wornLookId).toBe(scene.wornLookId);
    expect(lookById(uploaded, MY_LOOK_ID)).toMatchObject({
      assetUrl: "blob:my-uploaded-look",
      sourceLabel: "我的上传 Look · 仅本机",
      needsBackdropRemoval: true
    });
  });

  it("replaces a previous upload rather than stacking duplicates", () => {
    const base = createCommunityScene();
    const first = replaceMyLook(base, {
      assetUrl: "blob:one",
      label: "one.png",
      kind: "local-upload"
    });
    const second = replaceMyLook(first, {
      assetUrl: "blob:two",
      label: "two.png",
      kind: "local-upload"
    });

    expect(second.looks).toHaveLength(base.looks.length + 1);
    expect(lookById(second, MY_LOOK_ID)?.assetUrl).toBe("blob:two");
  });

  it("records only meaningful style reactions in the local demo state", () => {
    const scene = selectPartyLook(createCommunityScene(), "curated-sweet");
    const reacted = reactToSelectedLook(scene, "layering");

    expect(reacted.selectedReaction).toBe("layering");
    expect(reacted.reactions).toEqual(["palette", "layering", "remix"]);
    expect(selectPartyLook(reacted, "curated-mint").selectedReaction).toBeNull();
  });

  it("collects curated pixel Looks without pretending to persist community data", () => {
    const scene = createCommunityScene({
      assetUrl: "blob:mine",
      label: "mine.png",
      kind: "local-upload"
    });
    const saved = toggleSavedLook(scene, "curated-mint");
    const removed = toggleSavedLook(saved, "curated-mint");

    expect(saved.savedLookIds).toEqual(["curated-mint"]);
    expect(removed.savedLookIds).toEqual([]);
    expect(toggleSavedLook(scene, MY_LOOK_ID)).toBe(scene);
  });

  it("random dressing always lands on a Look the player is not wearing", () => {
    const scene = createCommunityScene();

    [0, 0.34, 0.67, 0.99].forEach((pick) => {
      const next = randomOtherLook(scene, pick);
      expect(next.wornLookId).not.toBe(scene.wornLookId);
      expect(lookById(next, next.wornLookId)).toBeDefined();
    });
  });
});
