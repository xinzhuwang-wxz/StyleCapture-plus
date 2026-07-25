export type ScenePoint = {
  x: number;
  y: number;
};

export type CommunityReaction = "heart" | "sparkle" | "music" | "wave";

export type CommunityResident = {
  id: string;
  name: string;
  label: "场景居民";
  publicTags: readonly string[];
  position: ScenePoint;
  accent: string;
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
  };
  residents: readonly CommunityResident[];
};

const reactions: readonly CommunityReaction[] = ["heart", "sparkle", "music", "wave"];

const residents: readonly CommunityResident[] = [
  {
    id: "resident-lilac",
    name: "紫丁香",
    label: "场景居民",
    publicTags: ["甜酷", "周末舞会"],
    position: { x: 28, y: 28 },
    accent: "#dca4ff"
  },
  {
    id: "resident-amber",
    name: "琥珀",
    label: "场景居民",
    publicTags: ["复古", "派对穿搭"],
    position: { x: 78, y: 24 },
    accent: "#ffbe7a"
  },
  {
    id: "resident-mint",
    name: "薄荷",
    label: "场景居民",
    publicTags: ["清新", "今晚出片"],
    position: { x: 74, y: 74 },
    accent: "#93e3cd"
  }
];

export function createCommunityScene(): CommunityScene {
  return {
    bounds: { minX: 8, maxX: 92, minY: 12, maxY: 86 },
    danceFloor: { minX: 37, maxX: 65, minY: 31, maxY: 63 },
    reactions,
    avatar: { x: 18, y: 70, isDancing: false, reaction: null },
    residents
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

export function selectReaction(
  scene: CommunityScene,
  reaction: CommunityReaction
): CommunityScene {
  return { ...scene, avatar: { ...scene.avatar, reaction } };
}
