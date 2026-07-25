export type CommunityAvatarSource = {
  assetUrl: string;
  label: string;
  kind: "demo-fallback" | "public-render-artifact";
  presentation?: "avatar" | "card";
};

export type PartyReaction = "palette" | "layering" | "remix";
export type PartyStage = "gallery" | "entrance" | "spotlight";

export type PartyLook = {
  id: string;
  title: string;
  assetUrl: string;
  alt: string;
  sourceKind: "my-look" | "curated-seed";
  sourceLabel: string;
  presentation: "avatar" | "card";
  tags: readonly string[];
  description: string;
  outfitFormula: readonly string[];
};

export type CommunityScene = {
  theme: {
    title: string;
    eyebrow: string;
    promise: string;
    prompt: string;
  };
  looks: readonly PartyLook[];
  myLookId: string;
  selectedLookId: string;
  selectedReaction: PartyReaction | null;
  savedLookIds: readonly string[];
  stage: PartyStage;
  reactions: readonly PartyReaction[];
};

export const defaultCommunityAvatar: CommunityAvatarSource = {
  assetUrl: "/assets/char-default.png",
  label: "我的像素 Look",
  kind: "demo-fallback"
};

const curatedLooks: readonly PartyLook[] = [
  {
    id: "curated-vintage",
    title: "暖棕复古",
    assetUrl: "/assets/community/pixel-look-1.png",
    alt: "暖棕复古 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    presentation: "card",
    tags: ["复古棕调", "腰线清晰", "金色点睛"],
    description: "把成熟棕调穿得轻盈，适合花房里的暖光时刻。",
    outfitFormula: ["方领短袖", "高腰半裙", "同色手袋"]
  },
  {
    id: "curated-mint",
    title: "薄荷花园",
    assetUrl: "/assets/community/pixel-look-2.png",
    alt: "薄荷花园 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    presentation: "card",
    tags: ["轻柔层次", "粉绿配色", "长裙"],
    description: "薄荷针织叠一层花瓣粉，柔和但仍然有完整轮廓。",
    outfitFormula: ["薄荷针织", "粉色长裙", "花朵配饰"]
  },
  {
    id: "curated-sweet",
    title: "甜酷课后",
    assetUrl: "/assets/community/pixel-look-3.png",
    alt: "甜酷课后 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    presentation: "card",
    tags: ["甜酷", "上短下长", "松弛感"],
    description: "红色短上衣配宽松工装裤，让甜感有一点利落反差。",
    outfitFormula: ["红色短上衣", "宽松工装裤", "白色球鞋"]
  }
];

function myLook(source: CommunityAvatarSource): PartyLook {
  return {
    id: "my-look",
    title: "我的今晚 Look",
    assetUrl: source.assetUrl,
    alt: "我的像素 Look",
    sourceKind: "my-look",
    sourceLabel:
      source.kind === "public-render-artifact"
        ? "我的公开像素 Look"
        : "我的示例形象 · 接口可替换",
    presentation: source.presentation ?? "avatar",
    tags: ["我的衣橱", "可分享封面"],
    description: "把你的像素搭配带到主题舞台，让这套 Look 成为今晚的主角。",
    outfitFormula: ["我的像素 Look", "主题舞台", "分享卡"]
  };
}

export function createCommunityScene(
  avatarSource: CommunityAvatarSource = defaultCommunityAvatar
): CommunityScene {
  const ownLook = myLook(avatarSource);
  return {
    theme: {
      title: "花房晚宴",
      eyebrow: "STYLE PARTY · THEME 01",
      promise: "让每套像素搭配被看见、被收藏、被分享",
      prompt: "花朵、柔光、带一点复古——今晚你想怎样被记住？"
    },
    looks: [...curatedLooks, ownLook],
    myLookId: ownLook.id,
    selectedLookId: curatedLooks[0].id,
    selectedReaction: null,
    savedLookIds: [],
    stage: "gallery",
    reactions: ["palette", "layering", "remix"]
  };
}

export function selectPartyLook(
  scene: CommunityScene,
  lookId: string
): CommunityScene {
  if (!scene.looks.some((look) => look.id === lookId)) return scene;
  return {
    ...scene,
    selectedLookId: lookId,
    selectedReaction: null,
    stage: lookId === scene.myLookId ? "spotlight" : "gallery"
  };
}

export function enterMyLook(scene: CommunityScene): CommunityScene {
  return {
    ...scene,
    selectedLookId: scene.myLookId,
    selectedReaction: null,
    stage: "entrance"
  };
}

export function completeEntrance(scene: CommunityScene): CommunityScene {
  if (scene.stage !== "entrance") return scene;
  return { ...scene, stage: "spotlight" };
}

export function reactToSelectedLook(
  scene: CommunityScene,
  reaction: PartyReaction
): CommunityScene {
  if (!scene.reactions.includes(reaction)) return scene;
  return { ...scene, selectedReaction: reaction };
}

export function toggleSavedLook(
  scene: CommunityScene,
  lookId: string
): CommunityScene {
  const look = scene.looks.find((candidate) => candidate.id === lookId);
  if (!look || look.sourceKind !== "curated-seed") return scene;
  return {
    ...scene,
    savedLookIds: scene.savedLookIds.includes(lookId)
      ? scene.savedLookIds.filter((id) => id !== lookId)
      : [...scene.savedLookIds, lookId]
  };
}

export function selectedPartyLook(scene: CommunityScene): PartyLook {
  return (
    scene.looks.find((look) => look.id === scene.selectedLookId) ??
    scene.looks[0]
  );
}
