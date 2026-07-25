import {
  ONE_PIECE_CATEGORIES,
  SINGLETON_CATEGORIES,
  type CatalogCategory,
  type CatalogItem
} from "./catalog";

/**
 * 自由组合的品类硬规则。
 *
 * Issue #4：「硬规则在生成式重排前执行，能阻止连衣裙与上衣/下装冲突」——
 * 保存新穿搭前先跑这套确定性检查，不把它交给模型判断。
 */

export type ComboAudit =
  | { readonly ok: true }
  | { readonly ok: false; readonly reason: string };

const MINIMUM_ITEMS = 2;

function countByCategory(items: readonly CatalogItem[]): Map<CatalogCategory, number> {
  const counts = new Map<CatalogCategory, number>();
  items.forEach((item) => {
    counts.set(item.category, (counts.get(item.category) ?? 0) + 1);
  });
  return counts;
}

/** 「件 / 条 / 双」——提示语里用对量词，读起来才像人写的。 */
const MEASURE_WORDS: Partial<Record<CatalogCategory, string>> = {
  鞋子: "双",
  下装: "条",
  连衣裙: "条"
};

export function auditCombo(items: readonly CatalogItem[]): ComboAudit {
  if (items.length < MINIMUM_ITEMS) {
    return { ok: false, reason: `至少选 ${MINIMUM_ITEMS} 件才能搭一套哦` };
  }

  const counts = countByCategory(items);

  for (const category of SINGLETON_CATEGORIES) {
    const count = counts.get(category) ?? 0;
    if (count > 1) {
      const measure = MEASURE_WORDS[category] ?? "件";
      return { ok: false, reason: `选了 ${count} ${measure}${category}` };
    }
  }

  const hasOnePiece = ONE_PIECE_CATEGORIES.some((category) => (counts.get(category) ?? 0) > 0);
  const hasTop = (counts.get("上装") ?? 0) > 0;
  const hasBottom = (counts.get("下装") ?? 0) > 0;
  if (hasOnePiece && (hasTop || hasBottom)) {
    return { ok: false, reason: "连衣裙和上下装冲突了" };
  }

  return { ok: true };
}
