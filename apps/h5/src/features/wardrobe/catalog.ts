/**
 * 数字衣橱的演示目录。
 *
 * 图片是设计稿交付的真实素材：整套穿搭 3:4 像素图、单品 1:1 像素图、真实单品
 * 拼贴图，以及人工审核过的模特参考照。所有条目都属于 `curated_seed` 来源，
 * 不是模型运行时产物。
 *
 * Issue #1/#2 的真实入库链跑通后，这里会被 Product API 的 Item/Look 替换；
 * 目录的字段刻意贴着领域语言（category / ownership / slots）以便平移。
 */

export type CatalogCategory =
  | "上装"
  | "外套"
  | "连衣裙"
  | "下装"
  | "鞋子"
  | "包包"
  | "配饰";

export const ITEM_CATEGORIES: readonly CatalogCategory[] = [
  "上装",
  "外套",
  "连衣裙",
  "下装",
  "鞋子",
  "包包",
  "配饰"
];

/**
 * 与上下装冲突的「一件式」品类。自由组合的 AI 审核用它判断连衣裙不能和
 * 上装/下装同时出现。
 */
export const ONE_PIECE_CATEGORIES: readonly CatalogCategory[] = ["连衣裙"];

/** 同一套穿搭里最多只能出现一件的品类。 */
export const SINGLETON_CATEGORIES: readonly CatalogCategory[] = [
  "上装",
  "下装",
  "鞋子",
  "外套",
  "连衣裙"
];

export type CatalogItem = {
  readonly id: string;
  readonly name: string;
  readonly category: CatalogCategory;
  /** 1:1 像素单品图 */
  readonly imageUrl: string;
  readonly owned: boolean;
  readonly price: number;
  /** 星露谷图鉴式的一句话描述 */
  readonly lore: string;
  /** AI 风格解读 */
  readonly styleReading: string;
  /** 商品描述 */
  readonly description: string;
};

export type CatalogOutfit = {
  readonly id: string;
  readonly name: string;
  readonly style: string;
  readonly scene: string;
  /** 3:4 像素封面（curated_seed） */
  readonly pixelCoverUrl: string;
  /** 人工审核的模特参考照（curated_seed，非用户本人） */
  readonly modelPhotoUrl: string;
  readonly description: string;
  readonly itemIds: readonly string[];
};

export const CATALOG_ITEMS: readonly CatalogItem[] = [
  {
    id: "item-top-1",
    name: "黄色方领短袖",
    category: "上装",
    imageUrl: "/assets/item-top-1.png",
    owned: true,
    price: 129,
    lore: "「像午后三点的阳光，被剪成一件上衣。」",
    styleReading: "方领 + 芥末黄，把肤色提亮一个度；短款收腰，配高腰下装最显比例。",
    description: "弹力棉质方领短袖，肩线利落，久坐不变形。"
  },
  {
    id: "item-bottom-1",
    name: "棕色包臀半裙",
    category: "下装",
    imageUrl: "/assets/item-bottom-1.png",
    owned: true,
    price: 189,
    lore: "「巧克力融化前的那一秒。」",
    styleReading: "包臀直筒版型，膝上 3cm 是最显腿长的长度；棕色压住黄色的跳，很复古。",
    description: "水洗棕色斜纹布半裙，含腰带，后开叉方便走路。"
  },
  {
    id: "item-bag-1",
    name: "棕色皮质托特包",
    category: "包包",
    imageUrl: "/assets/item-bag-1.png",
    owned: false,
    price: 259,
    lore: "「装得下工作，也装得下下班后的散步。」",
    styleReading: "硬挺托特能装 A4，通勤气场立起来；同棕色系呼应下装。",
    description: "植鞣牛皮托特包，可放 13 寸笔电，附皮带扣装饰。"
  },
  {
    id: "item-shoe-1",
    name: "芥黄尖头高跟鞋",
    category: "鞋子",
    imageUrl: "/assets/item-shoe-1.png",
    owned: false,
    price: 199,
    lore: "「走路声音很清脆的那种自信。」",
    styleReading: "尖头 + 细跟把腿的线条拉直，和上衣同色更整体。",
    description: "7cm 细跟尖头单鞋，内里羊皮，前掌加垫。"
  },
  {
    id: "item-outer-1",
    name: "抹茶绿针织开衫",
    category: "外套",
    imageUrl: "/assets/item-outer-1.png",
    owned: true,
    price: 149,
    lore: "「抹茶淋在草莓牛奶上。」",
    styleReading: "低饱和抹茶绿压住粉裙的甜，撞色但一点都不吵。",
    description: "细针针织开衫，落肩袖，可当空调房外搭。"
  },
  {
    id: "item-dress-1",
    name: "粉色层叠吊带裙",
    category: "连衣裙",
    imageUrl: "/assets/item-dress-1.png",
    owned: true,
    price: 229,
    lore: "「裙摆里养了一整个春天。」",
    styleReading: "层层蛋糕摆裙走路会飘，配平底更松弛，配高跟更正式。",
    description: "四层褶皱棉纱吊带长裙，内衬不透，可调肩带。"
  },
  {
    id: "item-acc-1",
    name: "花朵多层项链",
    category: "配饰",
    imageUrl: "/assets/item-acc-1.png",
    owned: false,
    price: 89,
    lore: "「把一小捧野花挂在脖子上。」",
    styleReading: "多层花朵项链填满 V 区，甜美感全靠它点睛。",
    description: "合金镀金多层链，花朵与叶片珐琅工艺，长度可调。"
  },
  {
    id: "item-acc-2",
    name: "碎花编织手链",
    category: "配饰",
    imageUrl: "/assets/item-acc-2.png",
    owned: false,
    price: 49,
    lore: "「手腕上的一句小声的话。」",
    styleReading: "碎花手链和发圈同系列，细节呼应比堆量更高级。",
    description: "编织碎花手链，绿玉珠点缀，磁扣易穿戴。"
  },
  {
    id: "item-shoe-2",
    name: "棕色尖头平底鞋",
    category: "鞋子",
    imageUrl: "/assets/item-shoe-2.png",
    owned: false,
    price: 229,
    lore: "「适合走很远，也适合被牵着走。」",
    styleReading: "裸棕平底把甜度收一收，长裙配它能走一整天。",
    description: "尖头软底平底鞋，全皮内里，鞋跟 1.5cm。"
  },
  {
    id: "item-top-3",
    name: "红色排扣短袖",
    category: "上装",
    imageUrl: "/assets/item-top-3.png",
    owned: true,
    price: 99,
    lore: "「一颗小番茄的红。」",
    styleReading: "正红排扣短袖收上身，配阔腿裤是最省心的比例。",
    description: "坑条弹力棉短袖，前排贝母扣，可解两颗当领口。"
  },
  {
    id: "item-bottom-2",
    name: "灰色工装长裤",
    category: "下装",
    imageUrl: "/assets/item-bottom-2.png",
    owned: true,
    price: 169,
    lore: "「口袋里能装下一整天的偷懒。」",
    styleReading: "灰色工装把重心压低，口袋多，视觉上更松弛。",
    description: "水洗天丝工装长裤，抽绳裤脚，六口袋设计。"
  },
  {
    id: "item-shoe-3",
    name: "白色小星板鞋",
    category: "鞋子",
    imageUrl: "/assets/item-shoe-3.png",
    owned: true,
    price: 279,
    lore: "「每一步都像刚洗过。」",
    styleReading: "白板鞋是万能句号，红灰这套用它收尾最干净。",
    description: "牛皮小白鞋，星星侧标，橡胶厚底防滑。"
  }
];

/** 走「＋ 拍一件 / 从相册选」入库后新增的单品。 */
export const CAPTURED_ITEM: CatalogItem = {
  id: "item-acc-3",
  name: "印花雪纺发圈",
  category: "配饰",
  imageUrl: "/assets/item-acc-3.png",
  owned: true,
  price: 39,
  lore: "「顺手一扎，就有了心情。」",
  styleReading: "同系列碎花发圈，把头发和裙子连成一套。",
  description: "雪纺印花大肠发圈，不勒头，不留痕。"
};

export const CATALOG_OUTFITS: readonly CatalogOutfit[] = [
  {
    id: "look-retro-commute",
    name: "棕黄复古通勤",
    style: "复古",
    scene: "通勤",
    pixelCoverUrl: "/assets/pixel-1.png",
    modelPhotoUrl: "/assets/real-1.jpg",
    description:
      "棕色包臀半裙配芥末黄上衣，同色系撞出复古气质；裙长到膝盖，配尖头高跟能把腿显长一截。",
    itemIds: ["item-top-1", "item-bottom-1", "item-bag-1", "item-shoe-1"]
  },
  {
    id: "look-cream-date",
    name: "奶油甜心约会",
    style: "甜美",
    scene: "约会",
    pixelCoverUrl: "/assets/pixel-2.png",
    modelPhotoUrl: "/assets/real-2.jpg",
    description:
      "抹茶开衫叠穿粉色层叠长裙，撞色但都很低饱和；再点两件碎花小饰品，甜度刚刚好。",
    itemIds: [
      "item-outer-1",
      "item-dress-1",
      "item-acc-1",
      "item-acc-2",
      "item-shoe-2"
    ]
  },
  {
    id: "look-utility-daily",
    name: "工装休闲日常",
    style: "休闲",
    scene: "日常",
    pixelCoverUrl: "/assets/pixel-3.png",
    modelPhotoUrl: "/assets/real-3.jpg",
    description:
      "红色短袖收紧上身比例，灰色工装裤把重心压低，白板鞋收尾，随手一拍都很出片。",
    itemIds: ["item-top-3", "item-bottom-2", "item-shoe-3"]
  }
];

/** 演示用的形象照，用户可在「形象照管理」里增删和切换。 */
export const REFERENCE_PHOTOS: readonly string[] = [
  "/assets/real-1.jpg",
  "/assets/real-2.jpg",
  "/assets/real-3.jpg"
];

export function douyinShopUrl(keyword: string): string {
  return `https://www.douyin.com/search/${encodeURIComponent(keyword)}`;
}
