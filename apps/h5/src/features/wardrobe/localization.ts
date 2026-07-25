const GARMENT_LABELS: Record<string, string> = {
  tops: "上装",
  bottoms: "下装",
  dresses: "连衣裙",
  outerwear: "外套",
  shoes: "鞋履",
  bags: "包袋",
  headwear: "帽饰",
  accessories: "配饰",
  beauty_other: "美妆及其他",
  t_shirt: "T 恤",
  shirt: "衬衫",
  blouse: "女式衬衫",
  knitwear: "针织衫",
  sweatshirt: "卫衣",
  tank_top: "背心",
  vest: "马甲",
  trousers: "长裤",
  jeans: "牛仔裤",
  shorts: "短裤",
  skirt: "半身裙",
  leggings: "紧身裤",
  dress: "连衣裙",
  jumpsuit: "连体裤",
  romper: "连身短裤",
  jacket: "夹克",
  coat: "大衣",
  trench_coat: "风衣",
  blazer: "西装外套",
  cardigan: "开衫",
  sneakers: "运动鞋",
  boots: "靴子",
  loafers: "乐福鞋",
  heels: "高跟鞋",
  sandals: "凉鞋",
  flats: "平底鞋",
  handbag: "手提包",
  shoulder_bag: "单肩包",
  crossbody_bag: "斜挎包",
  backpack: "双肩包",
  tote: "托特包",
  clutch: "手拿包",
  cap: "鸭舌帽",
  hat: "帽子",
  beanie: "针织帽",
  headband: "发带",
  scarf: "围巾",
  belt: "腰带",
  necklace: "项链",
  earrings: "耳饰",
  bracelet: "手链",
  watch: "腕表",
  glasses: "眼镜",
  beauty: "美妆",
  other: "其他"
};

export const GARMENT_CATEGORY_OPTIONS = [
  "tops",
  "bottoms",
  "dresses",
  "outerwear",
  "shoes",
  "bags",
  "headwear",
  "accessories",
  "beauty_other"
] as const;

export const LOOK_ANALYSIS_LABELS: Record<string, string> = {
  color: "配色",
  silhouette: "廓形",
  material: "材质",
  layering: "层次",
  focal_point: "视觉重点",
  scene: "适用场景",
  style: "整体风格"
};

export function garmentLabel(value: unknown, fallback = "待分类"): string {
  const key = String(value ?? "").trim();
  return GARMENT_LABELS[key] ?? (key.replaceAll("_", " ") || fallback);
}

export function garmentImageAlt(value: unknown, fallback = "穿搭单品"): string {
  return garmentLabel(value, fallback);
}
