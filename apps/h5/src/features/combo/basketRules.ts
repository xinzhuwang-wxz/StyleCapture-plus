/**
 * 组合衣柜的篮子。
 *
 * 「AI 会先检查品类有没有重复」这条规则不在这里重写——`wardrobe/comboRules.ts`
 * 已经实现了（连衣裙与上下装冲突、单品类只能一件、量词用对），这里只负责把
 * 衣橱单品翻译成它认识的品类，然后转交。
 */

import type { Item } from "../../api/client";
import {
  auditCombo,
  type ComboAudit,
  type ComboCategory
} from "../wardrobe/comboRules";

/**
 * 后端给的是英文品类 slug，规则模块说的是中文品类。
 * 帽饰和配饰在搭配规则上是一类，都可以戴多件。
 */
const CATEGORY_BY_SLUG: Record<string, ComboCategory> = {
  tops: "上装",
  bottoms: "下装",
  dresses: "连衣裙",
  outerwear: "外套",
  shoes: "鞋子",
  bags: "包袋",
  headwear: "配饰",
  accessories: "配饰",
  beauty_other: "妆容"
};

export const MAX_BASKET_ITEMS = 8;

export type BasketEntry = {
  itemId: string;
  category: ComboCategory | null;
  label: string;
  imageUrl: string | null;
};

/** 认不出品类时返回 null——规则层宁可不判，也不该瞎归类。 */
export function comboCategoryOf(item: Item): ComboCategory | null {
  const slug = item.attributes?.category?.value;
  return (typeof slug === "string" ? CATEGORY_BY_SLUG[slug] : undefined) ?? null;
}

export function basketEntryOf(item: Item, label: string): BasketEntry {
  return {
    itemId: item.id,
    category: comboCategoryOf(item),
    label,
    // 跟卡片取同一张图。种子单品没有 display_image_url，只有像素图，用后者
    // 会让篮子里全是灰块——走查截图就是这么发现的。?v= 与卡片保持一致，
    // 像素图重新生成后不会读到缓存里的旧图。
    imageUrl: item.pixel_image_url
      ? `${item.pixel_image_url}?v=${encodeURIComponent(item.updated_at)}`
      : item.display_image_url ?? null
  };
}

export function isInBasket(
  basket: readonly BasketEntry[],
  itemId: string
): boolean {
  return basket.some((entry) => entry.itemId === itemId);
}

export function addToBasket(
  basket: readonly BasketEntry[],
  entry: BasketEntry
): readonly BasketEntry[] {
  if (isInBasket(basket, entry.itemId)) return basket;
  if (basket.length >= MAX_BASKET_ITEMS) return basket;
  return [...basket, entry];
}

export function removeFromBasket(
  basket: readonly BasketEntry[],
  itemId: string
): readonly BasketEntry[] {
  return basket.filter((entry) => entry.itemId !== itemId);
}

/**
 * 篮子当前能不能存成一套。
 *
 * 品类未知的单品不参与硬规则判断——它们可能是任何东西，硬套规则只会误报。
 */
export function auditBasket(basket: readonly BasketEntry[]): ComboAudit {
  const known = basket
    .filter((entry) => entry.category !== null)
    .map((entry) => ({ category: entry.category as ComboCategory }));
  if (known.length < basket.length && known.length < 2) {
    // 已知品类不足两件，规则给不出有意义的结论。
    return basket.length >= 2
      ? { ok: true }
      : { ok: false, reason: "至少选 2 件才能搭一套哦" };
  }
  return auditCombo(known);
}
