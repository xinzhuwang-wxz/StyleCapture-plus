/**
 * Scene maps are data, not drawing code.
 *
 * The previous ballroom was a hardcoded sequence of `fillRect` calls, which made
 * a second backdrop mean a second renderer. A scene now declares a tile legend,
 * a grid of tile keys, and prop placements, so adding a location is content.
 *
 * Every `ground` row is exactly `COLUMNS` characters wide.
 */

export type TilePattern =
  | "flat"
  | "checker"
  | "planks"
  | "carpet"
  | "grass"
  | "path"
  | "water"
  | "glass"
  | "hedge"
  | "brick"
  | "rug";

export type TileStyle = {
  base: string;
  accent?: string;
  pattern?: TilePattern;
  /** Blocks walking. Walls, hedges and water are solid; decorated floor is not. */
  solid?: boolean;
  /** Draws the tile raised with a visible side face, giving the runway height. */
  elevation?: number;
  /** Side face colour for elevated tiles. */
  riser?: string;
};

export type PropKind =
  | "plant"
  | "sofa"
  | "painting"
  | "lamp"
  | "arch"
  | "chandelier"
  | "planter"
  | "banner"
  | "counter";

export type PropPlacement = {
  kind: PropKind;
  /** World units, measured at the prop's base so props y-sort with people. */
  x: number;
  y: number;
  scale?: number;
  flip?: boolean;
  /** Ceiling fixtures draw above everyone and skip y-sort. */
  overhead?: boolean;
};

export type SceneMap = {
  id: string;
  title: string;
  eyebrow: string;
  /** One line explaining the location, shown when the backdrop changes. */
  mood: string;
  /** What kind of gathering this is: a ball, a party, dropping by. */
  occasion: string;
  /** Why these people are in this room together. */
  premise: string;
  tile: number;
  legend: Record<string, TileStyle>;
  ground: readonly string[];
  props: readonly PropPlacement[];
  /** Colour behind everything. */
  backdrop: string;
  /** Warm or cool light wash over the whole scene. */
  ambience: string;
  /** Where the runway walk ends and the hero pose happens, in world units. */
  stagePoint: { x: number; y: number };
  /** Where the player enters from. */
  backstagePoint: { x: number; y: number };
  /** Loitering anchors for preset guests, in world units. */
  guestSpots: readonly { x: number; y: number }[];
};

export const TILE_SIZE = 16;

const greenhouse: SceneMap = {
  id: "greenhouse-ball",
  title: "花房夜宴",
  eyebrow: "THEME 01",
  mood: "玻璃花房里的夜场走秀，暖灯、藤蔓，和一条会发光的 T 台。",
  occasion: "主题走秀舞会",
  premise: "Lion 攒的月度主题夜，规则只有一条：穿一套你今晚想被记住的 Look。",
  tile: TILE_SIZE,
  backdrop: "#241539",
  ambience: "rgba(255, 183, 214, 0.10)",
  legend: {
    W: { base: "#3d2a5c", accent: "#7259a4", pattern: "glass", solid: true },
    H: { base: "#2f5b41", accent: "#43815a", pattern: "hedge", solid: true },
    c: { base: "#c9a68f", accent: "#b8927a", pattern: "flat" },
    f: { base: "#efdcc9", accent: "#e6cdb5", pattern: "checker" },
    d: { base: "#f7e9dc", accent: "#ecd8c4", pattern: "planks" },
    R: {
      base: "#e0648f",
      accent: "#f288ae",
      pattern: "carpet",
      elevation: 6,
      riser: "#8e3660"
    },
    ".": { base: "#241539", pattern: "flat", solid: true }
  },
  ground: [
    "..............................",
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
    "HHccccccccccccccccccccccccccHH",
    "ffffffffffffffffffffffffffffff",
    "ffffffffffffffffffffffffffffff",
    "fffffffffffffRRRRfffffffffffff",
    "fffffffffffffRRRRfffffffffffff",
    "ffffddddddfffRRRRfffddddddffff",
    "ffffddddddfffRRRRfffddddddffff",
    "ffffddddddfffRRRRfffddddddffff",
    "ffffddddddfffRRRRfffddddddffff",
    "ffffddddddfffRRRRfffddddddffff",
    "ffffddddddfffRRRRfffddddddffff",
    "fffffffffffffRRRRfffffffffffff",
    "fffffffffffffRRRRfffffffffffff",
    "ffffffffffffffffffffffffffffff",
    "ffffffffffffffffffffffffffffff",
    "ffffffffffffffffffffffffffffff",
    "ffffffffffffffffffffffffffffff",
    "HHffffffffffffffffffffffffffHH",
    "HHffffffffffffffffffffffffffHH",
    "ffffffffffffffffffffffffffffff",
    "ffffffffffffffffffffffffffffff",
    "ffffffffffffffffffffffffffffff",
    "ffffffffffffffffffffffffffffff",
    "ffffffffffffffffffffffffffffff",
    "ffffffffffffffffffffffffffffff",
    "HHffffffffffffffffffffffffffHH",
    "HHffffffffffffffffffffffffffHH",
    "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHH",
    "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHH"
  ],
  props: [
    { kind: "chandelier", x: 240, y: 96, overhead: true },
    { kind: "arch", x: 240, y: 122 },
    { kind: "banner", x: 240, y: 122, overhead: true },
    { kind: "painting", x: 96, y: 84 },
    { kind: "painting", x: 384, y: 84 },
    { kind: "plant", x: 46, y: 150, scale: 1.15 },
    { kind: "plant", x: 434, y: 150, scale: 1.15, flip: true },
    { kind: "planter", x: 150, y: 168 },
    { kind: "planter", x: 330, y: 168, flip: true },
    { kind: "lamp", x: 190, y: 160 },
    { kind: "lamp", x: 290, y: 160 },
    { kind: "sofa", x: 74, y: 222 },
    { kind: "sofa", x: 406, y: 222, flip: true },
    { kind: "lamp", x: 190, y: 300 },
    { kind: "lamp", x: 290, y: 300 },
    { kind: "plant", x: 60, y: 352, scale: 0.95 },
    { kind: "plant", x: 420, y: 352, scale: 0.95, flip: true },
    { kind: "sofa", x: 96, y: 430 },
    { kind: "sofa", x: 384, y: 430, flip: true },
    { kind: "planter", x: 176, y: 452 },
    { kind: "planter", x: 304, y: 452, flip: true }
  ],
  stagePoint: { x: 240, y: 200 },
  backstagePoint: { x: 240, y: 480 },
  // Clustered in front of the runway near where the player arrives, so the
  // opening frame always contains people rather than an empty room.
  guestSpots: [
    { x: 168, y: 302 },
    { x: 312, y: 308 },
    { x: 148, y: 386 },
    { x: 332, y: 380 }
  ]
};

const rooftop: SceneMap = {
  id: "rooftop-garden",
  title: "天台花园",
  eyebrow: "THEME 02",
  mood: "城市天台的黄昏花园，草地、石板路，和一条木质长台。",
  occasion: "黄昏天台派对",
  premise: "散场后转场来的天台局，没有 dress code，谁想上台谁上。",
  tile: TILE_SIZE,
  backdrop: "#2b3357",
  ambience: "rgba(255, 201, 142, 0.13)",
  legend: {
    W: { base: "#3f4d7c", accent: "#6379b4", pattern: "glass", solid: true },
    H: { base: "#38624a", accent: "#4d8563", pattern: "hedge", solid: true },
    g: { base: "#5b9160", accent: "#6da76f", pattern: "grass" },
    p: { base: "#cbc3ae", accent: "#b3aa93", pattern: "path" },
    w: { base: "#4f83a8", accent: "#74adce", pattern: "water", solid: true },
    R: {
      base: "#c99c65",
      accent: "#b3874f",
      pattern: "planks",
      elevation: 5,
      riser: "#7d5a35"
    },
    ".": { base: "#2b3357", pattern: "flat", solid: true }
  },
  ground: [
    "..............................",
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
    "WWWWWWWWWWWWWWWWWWWWWWWWWWWWWW",
    "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHH",
    "gggggggggggggggggggggggggggggg",
    "ggwwwwggggggggggggggggggwwwwgg",
    "ggwwwwggggggggggggggggggwwwwgg",
    "ggggggggggpppRRRRpppgggggggggg",
    "ggggggggggpppRRRRpppgggggggggg",
    "ggggppppppppRRRRRRppppppppgggg",
    "ggggppppppppRRRRRRppppppppgggg",
    "ggggppppppppRRRRRRppppppppgggg",
    "ggggppppppppRRRRRRppppppppgggg",
    "ggggppppppppRRRRRRppppppppgggg",
    "ggggppppppppRRRRRRppppppppgggg",
    "ggggggggggpppRRRRpppgggggggggg",
    "ggggggggggpppRRRRpppgggggggggg",
    "gggggggggggggppggggggggggggggg",
    "gggggggggggggppggggggggggggggg",
    "gggggggggggggggggggggggggggggg",
    "gggggggggggggggggggggggggggggg",
    "ggwwwwggggggggggggggggggwwwwgg",
    "ggwwwwggggggggggggggggggwwwwgg",
    "gggggggggggggggggggggggggggggg",
    "gggggggggggggggggggggggggggggg",
    "gggggggggggggggggggggggggggggg",
    "gggggggggggggggggggggggggggggg",
    "gggggggggggggggggggggggggggggg",
    "gggggggggggggggggggggggggggggg",
    "HHggggggggggggggggggggggggggHH",
    "HHggggggggggggggggggggggggggHH",
    "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHH",
    "HHHHHHHHHHHHHHHHHHHHHHHHHHHHHH"
  ],
  props: [
    { kind: "arch", x: 240, y: 122 },
    { kind: "banner", x: 240, y: 122, overhead: true },
    { kind: "plant", x: 42, y: 160, scale: 1.2 },
    { kind: "plant", x: 438, y: 160, scale: 1.2, flip: true },
    { kind: "planter", x: 146, y: 172 },
    { kind: "planter", x: 334, y: 172, flip: true },
    { kind: "lamp", x: 178, y: 162 },
    { kind: "lamp", x: 302, y: 162 },
    { kind: "sofa", x: 78, y: 230 },
    { kind: "sofa", x: 402, y: 230, flip: true },
    { kind: "lamp", x: 178, y: 306 },
    { kind: "lamp", x: 302, y: 306 },
    { kind: "plant", x: 64, y: 352, scale: 1 },
    { kind: "plant", x: 416, y: 352, scale: 1, flip: true },
    { kind: "sofa", x: 100, y: 436 },
    { kind: "sofa", x: 380, y: 436, flip: true },
    { kind: "planter", x: 180, y: 456 },
    { kind: "planter", x: 300, y: 456, flip: true }
  ],
  stagePoint: { x: 240, y: 200 },
  backstagePoint: { x: 240, y: 480 },
  guestSpots: [
    { x: 168, y: 302 },
    { x: 312, y: 308 },
    { x: 148, y: 386 },
    { x: 332, y: 380 }
  ]
};

/**
 * A warm neighbourhood coffee house: exposed brick, a big rug, mismatched
 * couches and the little corner stage where whoever feels like it gets up and
 * performs. Drawn from the tile legend like every other scene — an homage to
 * the sitcom coffee-shop archetype, not a copy of any photograph.
 */
const coffeeHouse: SceneMap = {
  id: "coffee-house",
  title: "中央咖啡馆",
  eyebrow: "THEME 03",
  mood: "红砖墙、旧沙发和一块小舞台，谁都可以上去站两分钟。",
  occasion: "咖啡馆串门",
  premise: "没有主题也没有 dress code——下午没事，几个人窝在老位子上聊天。",
  tile: TILE_SIZE,
  backdrop: "#2a1c18",
  ambience: "rgba(255, 176, 92, 0.14)",
  legend: {
    B: { base: "#6d3b2c", accent: "#8a4c39", pattern: "brick", solid: true },
    c: { base: "#3f2a21", accent: "#573a2d", pattern: "flat" },
    k: { base: "#b98553", accent: "#a97444", pattern: "planks" },
    r: { base: "#8a4b46", accent: "#a35d55", pattern: "rug" },
    S: {
      base: "#7a4a30",
      accent: "#8f5a3a",
      pattern: "planks",
      elevation: 6,
      riser: "#4d2c1b"
    },
    ".": { base: "#2a1c18", pattern: "flat", solid: true }
  },
  ground: [
    "..............................",
    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    "BBccccccccccccccccccccccccccBB",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkkkkkkkSSSSSSSSkkkkkkkkkkk",
    "kkkkkkkkkkkSSSSSSSSkkkkkkkkkkk",
    "kkkkkkkkkkkSSSSSSSSkkkkkkkkkkk",
    "kkkkkkkkkkkSSSSSSSSkkkkkkkkkkk",
    "kkkkkkkkkkkSSSSSSSSkkkkkkkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkrrrrrrrrrrrrrrrrrrrrkkkkk",
    "kkkkkrrrrrrrrrrrrrrrrrrrrkkkkk",
    "kkkkkrrrrrrrrrrrrrrrrrrrrkkkkk",
    "kkkkkrrrrrrrrrrrrrrrrrrrrkkkkk",
    "kkkkkrrrrrrrrrrrrrrrrrrrrkkkkk",
    "kkkkkrrrrrrrrrrrrrrrrrrrrkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
    "BBkkkkkkkkkkkkkkkkkkkkkkkkkkBB",
    "BBkkkkkkkkkkkkkkkkkkkkkkkkkkBB",
    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
  ],
  props: [
    { kind: "counter", x: 372, y: 118 },
    { kind: "painting", x: 96, y: 86 },
    { kind: "painting", x: 148, y: 86 },
    { kind: "lamp", x: 176, y: 150 },
    { kind: "lamp", x: 304, y: 150 },
    { kind: "plant", x: 44, y: 152, scale: 1.1 },
    { kind: "plant", x: 452, y: 210, scale: 1 },
    { kind: "sofa", x: 128, y: 288, scale: 1.15 },
    { kind: "sofa", x: 352, y: 288, scale: 1.15, flip: true },
    { kind: "sofa", x: 240, y: 372, scale: 1.2 },
    { kind: "lamp", x: 72, y: 330 },
    { kind: "lamp", x: 408, y: 330 },
    { kind: "plant", x: 58, y: 420, scale: 0.95 },
    { kind: "plant", x: 422, y: 420, scale: 0.95, flip: true },
    { kind: "banner", x: 240, y: 118, overhead: true }
  ],
  stagePoint: { x: 240, y: 184 },
  backstagePoint: { x: 240, y: 470 },
  guestSpots: [
    { x: 168, y: 300 },
    { x: 312, y: 306 },
    { x: 148, y: 386 },
    { x: 332, y: 380 }
  ]
};

export const sceneMaps: readonly SceneMap[] = [
  greenhouse,
  rooftop,
  coffeeHouse
];

export function sceneById(id: string): SceneMap {
  return sceneMaps.find((scene) => scene.id === id) ?? sceneMaps[0];
}

export function mapSize(scene: SceneMap): { width: number; height: number } {
  const columns = Math.max(...scene.ground.map((row) => row.length));
  return {
    width: columns * scene.tile,
    height: scene.ground.length * scene.tile
  };
}

export function tileAt(scene: SceneMap, x: number, y: number): TileStyle | null {
  const column = Math.floor(x / scene.tile);
  const row = Math.floor(y / scene.tile);
  const line = scene.ground[row];
  if (!line) return null;
  const key = line[column];
  if (!key) return null;
  return scene.legend[key] ?? null;
}

/** Walkable means inside the map and not standing on a solid tile. */
export function canStand(scene: SceneMap, x: number, y: number): boolean {
  const style = tileAt(scene, x, y);
  return style !== null && !style.solid;
}

/** True when the point is on the raised runway, used by the choreography. */
export function onRunway(scene: SceneMap, x: number, y: number): boolean {
  return (tileAt(scene, x, y)?.elevation ?? 0) > 0;
}
