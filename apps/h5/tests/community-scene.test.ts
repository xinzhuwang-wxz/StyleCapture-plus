import {
  completeEntrance,
  createCommunityScene,
  enterMyLook,
  reactToSelectedLook,
  selectPartyLook,
  toggleSavedLook
} from "../src/features/community/communityScene";

describe("theme party scene", () => {
  it("starts as a truthful curated showcase with the user's real pixel asset available", () => {
    const scene = createCommunityScene({
      assetUrl: "/assets/my-pixel-look.png",
      label: "我的公开像素 Look",
      kind: "public-render-artifact"
    });

    expect(scene.theme).toMatchObject({
      title: "花房晚宴",
      promise: "让每套像素搭配被看见、被收藏、被分享"
    });
    expect(scene.looks[0]).toMatchObject({
      sourceKind: "curated-seed",
      sourceLabel: "精选示例 · 非真人"
    });
    expect(scene.looks.find((look) => look.id === scene.myLookId)).toMatchObject({
      assetUrl: "/assets/my-pixel-look.png",
      sourceKind: "my-look"
    });
  });

  it("lets the user browse inspiration, then brings their own Look to the spotlight", () => {
    const scene = createCommunityScene();
    const selected = selectPartyLook(scene, "curated-mint");
    const entering = enterMyLook(selected);
    const spotlight = completeEntrance(entering);

    expect(selected.selectedLookId).toBe("curated-mint");
    expect(entering).toMatchObject({
      selectedLookId: scene.myLookId,
      stage: "entrance",
      selectedReaction: null
    });
    expect(spotlight.stage).toBe("spotlight");
  });

  it("records only meaningful style reactions in the local demo state", () => {
    const scene = selectPartyLook(createCommunityScene(), "curated-sweet");
    const reacted = reactToSelectedLook(scene, "layering");

    expect(reacted.selectedReaction).toBe("layering");
    expect(reacted.reactions).toEqual(["palette", "layering", "remix"]);
  });

  it("collects curated pixel Looks without pretending to persist community data", () => {
    const scene = createCommunityScene();
    const saved = toggleSavedLook(scene, "curated-mint");
    const removed = toggleSavedLook(saved, "curated-mint");

    expect(saved.savedLookIds).toEqual(["curated-mint"]);
    expect(removed.savedLookIds).toEqual([]);
    expect(toggleSavedLook(scene, scene.myLookId)).toBe(scene);
  });
});
