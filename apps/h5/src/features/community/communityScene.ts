/**
 * Look catalogue and social state for the Style Party.
 *
 * The stage/choreography state lives in `world/simulation.ts`; this module only
 * knows which Looks exist, which one the player is wearing, and what the player
 * has reacted to or collected. All of it is local to the session.
 */

export type CommunityAvatarSource = {
  assetUrl: string;
  label: string;
  kind: "demo-fallback" | "local-upload" | "public-render-artifact";
};

export type PartyReaction = "palette" | "layering" | "remix";

export type PartyLook = {
  id: string;
  title: string;
  assetUrl: string;
  alt: string;
  sourceKind: "my-look" | "curated-seed";
  sourceLabel: string;
  /** Bundled Looks are pre-cut; user images still carry a card backdrop. */
  needsBackdropRemoval: boolean;
  /**
   * Folder of authored poses. Looks that have one swap real artwork per state;
   * the rest rely on the procedural rig alone.
   */
  poseRoot?: string;
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
  /** The Look the player's character is wearing right now. */
  wornLookId: string;
  /** The Look shown in the detail panel. */
  selectedLookId: string;
  selectedReaction: PartyReaction | null;
  savedLookIds: readonly string[];
  reactions: readonly PartyReaction[];
};

export const defaultCommunityAvatar: CommunityAvatarSource = {
  assetUrl: "/assets/community/cutouts/pixel-look-3.png",
  label: "我的像素 Look",
  kind: "demo-fallback"
};

const poseRootFor = (character: string) =>
  `/assets/community/poses/${character}`;

/** Looks drawn from the authored pose pack: four states of real artwork each. */
const animatedLooks: readonly PartyLook[] = [
  {
    id: "pose-cargo",
    title: "甜酷工装",
    assetUrl: `${poseRootFor("cargo")}/idle.png`,
    alt: "甜酷工装 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    needsBackdropRemoval: false,
    poseRoot: poseRootFor("cargo"),
    tags: ["甜酷", "上短下长", "松弛感"],
    description: "红色短上衣配宽松工装裤，甜里带一点利落反差。",
    outfitFormula: ["红色短上衣", "宽松工装裤", "白色球鞋"]
  },
  {
    id: "pose-ash",
    title: "灰调长裙",
    assetUrl: `${poseRootFor("ash")}/idle.png`,
    alt: "灰调长裙 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    needsBackdropRemoval: false,
    poseRoot: poseRootFor("ash"),
    tags: ["极简灰", "长裙", "安静感"],
    description: "上下同色的灰调，把长度和垂坠感留给裙子。",
    outfitFormula: ["米灰针织", "灰色长裙", "浅色平底鞋"]
  },
  {
    id: "pose-jersey",
    title: "球衣迷彩",
    assetUrl: `${poseRootFor("jersey")}/idle.png`,
    alt: "球衣迷彩 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    needsBackdropRemoval: false,
    poseRoot: poseRootFor("jersey"),
    tags: ["运动感", "撞色", "迷彩短裤"],
    description: "条纹球衣配迷彩短裤，用配饰把运动感收回来。",
    outfitFormula: ["条纹球衣", "迷彩短裤", "黑色短靴"]
  },
  {
    id: "pose-crew-wide",
    title: "活动衫阔腿裤",
    assetUrl: `${poseRootFor("crew-wide")}/idle.png`,
    alt: "活动衫阔腿裤 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    needsBackdropRemoval: false,
    poseRoot: poseRootFor("crew-wide"),
    tags: ["活动限定", "阔腿裤", "耐穿一整天"],
    description: "黑色活动 T 恤配浅蓝阔腿裤，站一天也不皱。",
    outfitFormula: ["黑色活动 T", "浅蓝阔腿裤", "白色板鞋"]
  },
  {
    id: "pose-crew-glasses",
    title: "工牌黑T",
    assetUrl: `${poseRootFor("crew-glasses")}/idle.png`,
    alt: "工牌黑T Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    needsBackdropRemoval: false,
    poseRoot: poseRootFor("crew-glasses"),
    tags: ["利落", "全黑", "工牌"],
    description: "全黑一身加一副眼镜，最省心也最不会错。",
    outfitFormula: ["黑色活动 T", "深色牛仔裤", "帆布鞋"]
  },
  {
    id: "pose-visitor-skirt",
    title: "白T百褶裙",
    assetUrl: `${poseRootFor("visitor-skirt")}/idle.png`,
    alt: "白T百褶裙 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    needsBackdropRemoval: false,
    poseRoot: poseRootFor("visitor-skirt"),
    tags: ["出片", "百褶裙", "墨镜"],
    description: "印花白 T 塞进百褶裙，配马丁靴和不摘的墨镜。",
    outfitFormula: ["印花白 T", "黑色百褶裙", "棕色短靴"]
  },
  {
    id: "pose-linen",
    title: "白衬衫日",
    assetUrl: `${poseRootFor("linen")}/idle.png`,
    alt: "白衬衫日 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    needsBackdropRemoval: false,
    poseRoot: poseRootFor("linen"),
    tags: ["全白", "利落", "通勤"],
    description: "全白一身，靠版型和材质做出层次。",
    outfitFormula: ["白色短袖衬衫", "白色长裤", "白色球鞋"]
  }
];

const curatedLooks: readonly PartyLook[] = [
  {
    id: "curated-vintage",
    title: "暖棕复古",
    assetUrl: "/assets/community/cutouts/pixel-look-1.png",
    alt: "暖棕复古 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    needsBackdropRemoval: false,
    tags: ["复古棕调", "腰线清晰", "金色点睛"],
    description: "把成熟棕调穿得轻盈，适合花房里的暖光时刻。",
    outfitFormula: ["方领短袖", "高腰半裙", "同色手袋"]
  },
  {
    id: "curated-mint",
    title: "薄荷花园",
    assetUrl: "/assets/community/cutouts/pixel-look-2.png",
    alt: "薄荷花园 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    needsBackdropRemoval: false,
    tags: ["轻柔层次", "粉绿配色", "长裙"],
    description: "薄荷针织叠一层花瓣粉，柔和但仍然有完整轮廓。",
    outfitFormula: ["薄荷针织", "粉色长裙", "花朵配饰"]
  },
  {
    id: "curated-sweet",
    title: "甜酷课后",
    assetUrl: "/assets/community/cutouts/pixel-look-3.png",
    alt: "甜酷课后 Look 像素形象",
    sourceKind: "curated-seed",
    sourceLabel: "精选示例 · 非真人",
    needsBackdropRemoval: false,
    tags: ["甜酷", "上短下长", "松弛感"],
    description: "红色短上衣配宽松工装裤，让甜感有一点利落反差。",
    outfitFormula: ["红色短上衣", "宽松工装裤", "白色球鞋"]
  }
];

export const MY_LOOK_ID = "my-look";

function myLook(source: CommunityAvatarSource): PartyLook {
  return {
    id: MY_LOOK_ID,
    title: "我的像素 Look",
    assetUrl: source.assetUrl,
    alt: "我的像素 Look",
    sourceKind: "my-look",
    sourceLabel:
      source.kind === "local-upload"
        ? "我的上传 Look · 仅本机"
        : source.kind === "public-render-artifact"
          ? "我的公开像素 Look"
          : "我的示例形象 · 接口可替换",
    needsBackdropRemoval: source.kind !== "demo-fallback",
    tags: ["我的衣橱", "可分享封面"],
    description: "把你的像素搭配带到主题舞台，让这套 Look 成为今晚的主角。",
    outfitFormula: ["我的像素 Look", "主题舞台", "分享卡"]
  };
}

export function createCommunityScene(
  avatarSource?: CommunityAvatarSource
): CommunityScene {
  const catalogue = [...animatedLooks, ...curatedLooks];
  const looks = avatarSource
    ? [...catalogue, myLook(avatarSource)]
    : catalogue;
  // Every authored pose set is worn by a guest, so the player starts in a Look
  // nobody else has. Choosing an animated Look from the rail is then a visible
  // decision rather than an accidental twin.
  const worn = avatarSource ? MY_LOOK_ID : curatedLooks[0].id;
  return {
    theme: {
      title: "花房夜宴",
      eyebrow: "STYLE PARTY · THEME 01",
      promise: "让每套像素搭配被看见、被收藏、被分享",
      prompt: "花朵、柔光、带一点复古——今晚你想怎样被记住？"
    },
    looks,
    wornLookId: worn,
    selectedLookId: curatedLooks[0].id,
    selectedReaction: null,
    savedLookIds: [],
    reactions: ["palette", "layering", "remix"]
  };
}

export function lookById(
  scene: CommunityScene,
  id: string
): PartyLook | undefined {
  return scene.looks.find((look) => look.id === id);
}

export function wornLook(scene: CommunityScene): PartyLook {
  return lookById(scene, scene.wornLookId) ?? scene.looks[0];
}

export function selectedPartyLook(scene: CommunityScene): PartyLook {
  return lookById(scene, scene.selectedLookId) ?? scene.looks[0];
}

/** Changes the whole outfit; per-item dressing is a later slice. */
export function wearLook(scene: CommunityScene, lookId: string): CommunityScene {
  if (!lookById(scene, lookId)) return scene;
  return { ...scene, wornLookId: lookId, selectedLookId: lookId };
}

export function selectPartyLook(
  scene: CommunityScene,
  lookId: string
): CommunityScene {
  if (!lookById(scene, lookId)) return scene;
  return { ...scene, selectedLookId: lookId, selectedReaction: null };
}

/** Adds or replaces the player's own Look from a local image. */
export function replaceMyLook(
  scene: CommunityScene,
  source: CommunityAvatarSource
): CommunityScene {
  const replacement = myLook(source);
  const looks = lookById(scene, MY_LOOK_ID)
    ? scene.looks.map((look) => (look.id === MY_LOOK_ID ? replacement : look))
    : [...scene.looks, replacement];
  return {
    ...scene,
    looks,
    selectedLookId: MY_LOOK_ID,
    selectedReaction: null
  };
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
  const look = lookById(scene, lookId);
  if (!look || look.sourceKind !== "curated-seed") return scene;
  return {
    ...scene,
    savedLookIds: scene.savedLookIds.includes(lookId)
      ? scene.savedLookIds.filter((id) => id !== lookId)
      : [...scene.savedLookIds, lookId]
  };
}

/** Picks a Look the player is not already wearing. */
export function randomOtherLook(
  scene: CommunityScene,
  pick: number
): CommunityScene {
  const candidates = scene.looks.filter((look) => look.id !== scene.wornLookId);
  if (!candidates.length) return scene;
  const index = Math.abs(Math.floor(pick * candidates.length)) % candidates.length;
  return wearLook(scene, candidates[index].id);
}
