export type ScenePoint = {
  x: number;
  y: number;
};

export type CommunityReaction = "heart" | "sparkle" | "music" | "wave";

export type PixelDollProfile = {
  hair: string;
  hairStyle: "curly" | "bob" | "long" | "twin";
  skin: string;
  outfit: string;
  trim: string;
  shoes: string;
  blush: string;
  dressShape: "a-line" | "pleated" | "jacket" | "two-piece";
  accessory: "ribbon" | "handbag" | "beret" | "necklace" | "bow" | "none";
};

export type CommunityResident = {
  id: string;
  name: string;
  label: "场景居民";
  publicTags: readonly string[];
  position: ScenePoint;
  accent: string;
  doll: PixelDollProfile;
};

export type RunwayState = {
  featuredAvatar: "me" | null;
  applause: number;
  isShowing: boolean;
};

export type CommunityScene = {
  bounds: {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
  };
  danceFloor: {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
  };
  reactions: readonly CommunityReaction[];
  avatar: ScenePoint & {
    isDancing: boolean;
    reaction: CommunityReaction | null;
    doll: PixelDollProfile;
  };
  runway: RunwayState;
  residents: readonly CommunityResident[];
  audience: readonly PixelDollProfile[];
};

const reactions: readonly CommunityReaction[] = ["heart", "sparkle", "music", "wave"];

const residents: readonly CommunityResident[] = [
  {
    id: "resident-lilac",
    name: "紫丁香",
    label: "场景居民",
    publicTags: ["甜酷", "周末舞会"],
    position: { x: 28, y: 28 },
    accent: "#dca4ff",
    doll: {
      hair: "#5b3554",
      hairStyle: "long",
      skin: "#f8d1b7",
      outfit: "#dca4ff",
      trim: "#fff1fb",
      shoes: "#5d3e61",
      blush: "#e982a7",
      dressShape: "a-line",
      accessory: "ribbon"
    }
  },
  {
    id: "resident-amber",
    name: "琥珀",
    label: "场景居民",
    publicTags: ["复古", "派对穿搭"],
    position: { x: 78, y: 24 },
    accent: "#ffbe7a",
    doll: {
      hair: "#5f3b29",
      hairStyle: "bob",
      skin: "#f2be9d",
      outfit: "#ffbe7a",
      trim: "#fff0c3",
      shoes: "#624437",
      blush: "#d97077",
      dressShape: "jacket",
      accessory: "beret"
    }
  },
  {
    id: "resident-mint",
    name: "薄荷",
    label: "场景居民",
    publicTags: ["清新", "今晚出片"],
    position: { x: 74, y: 74 },
    accent: "#93e3cd",
    doll: {
      hair: "#3d5a55",
      hairStyle: "twin",
      skin: "#e6ad8f",
      outfit: "#93e3cd",
      trim: "#edfffa",
      shoes: "#4c5964",
      blush: "#cc716f",
      dressShape: "two-piece",
      accessory: "handbag"
    }
  }
];

const audience: readonly PixelDollProfile[] = [
  {
    hair: "#654053",
    hairStyle: "curly",
    skin: "#f0c2a8",
    outfit: "#ed68aa",
    trim: "#ffe3f2",
    shoes: "#5e3b5d",
    blush: "#d86f92",
    dressShape: "pleated",
    accessory: "ribbon"
  },
  {
    hair: "#3c3152",
    hairStyle: "long",
    skin: "#f3c6aa",
    outfit: "#fbdb83",
    trim: "#fff3ca",
    shoes: "#3b3553",
    blush: "#d77b86",
    dressShape: "a-line",
    accessory: "bow"
  },
  {
    hair: "#543e2e",
    hairStyle: "bob",
    skin: "#d99676",
    outfit: "#86e6cf",
    trim: "#e8fffa",
    shoes: "#4b475f",
    blush: "#bd635f",
    dressShape: "jacket",
    accessory: "necklace"
  },
  {
    hair: "#4a335f",
    hairStyle: "twin",
    skin: "#f4c3ae",
    outfit: "#9d68ff",
    trim: "#f0e7ff",
    shoes: "#51346b",
    blush: "#db7d9d",
    dressShape: "two-piece",
    accessory: "beret"
  },
  {
    hair: "#57302f",
    hairStyle: "curly",
    skin: "#c98267",
    outfit: "#ff9b7b",
    trim: "#ffe4dc",
    shoes: "#513842",
    blush: "#b85d62",
    dressShape: "pleated",
    accessory: "handbag"
  },
  {
    hair: "#2e4558",
    hairStyle: "long",
    skin: "#edbc9c",
    outfit: "#75d7ff",
    trim: "#e5faff",
    shoes: "#475466",
    blush: "#cf7383",
    dressShape: "a-line",
    accessory: "none"
  }
];

export function createCommunityScene(): CommunityScene {
  return {
    bounds: { minX: 8, maxX: 92, minY: 12, maxY: 86 },
    danceFloor: { minX: 37, maxX: 65, minY: 31, maxY: 63 },
    reactions,
    avatar: {
      x: 18,
      y: 70,
      isDancing: false,
      reaction: null,
      doll: {
        hair: "#6d3d3d",
        hairStyle: "curly",
        skin: "#f4c5ac",
        outfit: "#f6b6ca",
        trim: "#fff4fa",
        shoes: "#4b415f",
        blush: "#dc7890",
        dressShape: "a-line",
        accessory: "ribbon"
      }
    },
    runway: { featuredAvatar: null, applause: 0, isShowing: false },
    residents,
    audience
  };
}

export function moveAvatarTo(scene: CommunityScene, target: ScenePoint): CommunityScene {
  const x = Math.min(scene.bounds.maxX, Math.max(scene.bounds.minX, target.x));
  const y = Math.min(scene.bounds.maxY, Math.max(scene.bounds.minY, target.y));
  const isDancing =
    x >= scene.danceFloor.minX &&
    x <= scene.danceFloor.maxX &&
    y >= scene.danceFloor.minY &&
    y <= scene.danceFloor.maxY;

  return { ...scene, avatar: { ...scene.avatar, x, y, isDancing } };
}

export function sendAvatarToRunway(scene: CommunityScene): CommunityScene {
  return { ...scene, runway: { featuredAvatar: "me", applause: 12, isShowing: true } };
}

export function returnAvatarBackstage(scene: CommunityScene): CommunityScene {
  return { ...scene, runway: { ...scene.runway, isShowing: false } };
}

export function selectReaction(
  scene: CommunityScene,
  reaction: CommunityReaction
): CommunityScene {
  return { ...scene, avatar: { ...scene.avatar, reaction } };
}
