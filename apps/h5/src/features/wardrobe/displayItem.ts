import type { Item } from "../../api/client";
import {
  CAPTURED_ITEM,
  CATALOG_ITEMS,
  ITEM_CATEGORIES,
  type CatalogCategory,
  type CatalogItem
} from "./catalog";

/**
 * 把 Product API 的 Item 映射成衣橱 UI 用的展示模型。
 *
 * 目录里已有的条目直接复用（自带价格、图鉴文案和真实素材图）；用户刚通过拍照
 * 或 Feed 圈选入库的新 Item 没有这些人工文案，就按真实属性生成，缺什么如实空着，
 * 不编造价格或图鉴句子。
 */

const CATALOG_BY_ID = new Map<string, CatalogItem>(
  [...CATALOG_ITEMS, CAPTURED_ITEM].map((entry) => [entry.id, entry])
);

const CATEGORY_SET = new Set<string>(ITEM_CATEGORIES);

function normalizeCategory(value: string): CatalogCategory {
  return CATEGORY_SET.has(value) ? (value as CatalogCategory) : "配饰";
}

function attribute(item: Item, key: string): string | null {
  const field = item.attributes[key] as { value?: unknown } | undefined;
  const value = field?.value;
  return value === undefined || value === null ? null : String(value);
}

export function toDisplayItem(item: Item): CatalogItem {
  const catalog = CATALOG_BY_ID.get(item.id);
  if (catalog) return catalog;

  const category = normalizeCategory(attribute(item, "category") ?? "");
  const priceText = attribute(item, "price");

  return {
    id: item.id,
    name: attribute(item, "subcategory") ?? attribute(item, "category") ?? "新单品",
    category,
    imageUrl: item.source_image_url,
    owned: item.ownership === "owned",
    price: priceText ? Number(priceText) : 0,
    // 新入库的单品还没有人工写的图鉴文案，如实留白。
    lore: "「新朋友，还没写下图鉴。」",
    styleReading: "AI 还在看这件衣服～稍后会给出风格解读。",
    description: attribute(item, "description") ?? "暂无商品描述。"
  };
}

export function findDisplayItem(items: readonly Item[], itemId: string): CatalogItem | null {
  const fromApi = items.find((item) => item.id === itemId);
  if (fromApi) return toDisplayItem(fromApi);
  return CATALOG_BY_ID.get(itemId) ?? null;
}
