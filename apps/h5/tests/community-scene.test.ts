import {
  completeEntrance,
  createCommunityScene,
  enterMyLook,
  reactToSelectedLook,
  replaceMyLook,
  selectPartyLook,
  startDance,
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
      title: "花房夜宴",
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
      stage: "runway",
      selectedReaction: null
    });
    expect(spotlight.stage).toBe("spotlight");
  });

  it("keeps a local upload backstage until the user explicitly enters", () => {
    const scene = createCommunityScene();
    const uploaded = replaceMyLook(scene, {
      assetUrl: "blob:my-uploaded-look",
      label: "my-look.png",
      kind: "local-upload"
    });

    expect(uploaded).toMatchObject({
      selectedLookId: scene.myLookId,
      stage: "backstage",
      selectedReaction: null
    });
    expect(
      uploaded.looks.find((look) => look.id === uploaded.myLookId)
    ).toMatchObject({
      assetUrl: "blob:my-uploaded-look",
      sourceLabel: "我的上传 Look · 仅本机",
      presentation: "avatar"
    });
  });

  it("moves from runway to spotlight and then into the dance floor", () => {
    const runway = enterMyLook(createCommunityScene());
    const spotlight = completeEntrance(runway);
    const dancing = startDance(spotlight);

    expect(runway.stage).toBe("runway");
    expect(spotlight.stage).toBe("spotlight");
    expect(dancing.stage).toBe("dance");
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
