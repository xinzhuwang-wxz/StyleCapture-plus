/**
 * 自由组合的品类硬规则。
 *
 * 这层只做确定性结构校验，不保存结果，也不持有任何 mock/catalog 数据。
 * 保存穿搭时仍然必须调用后端真实搭配/Look API。
 */

export type ComboCategory =
  | "上装"
  | "下装"
  | "连衣裙"
  | "外套"
  | "鞋子"
  | "包袋"
  | "配饰"
  | "妆容"
  | "场景";

export type ComboRuleItem = {
  readonly category: ComboCategory;
};

export type ComboAudit =
  | { readonly ok: true }
  | { readonly ok: false; readonly reason: string };

const MINIMUM_ITEMS = 2;

const SINGLETON_CATEGORIES: readonly ComboCategory[] = [
  "上装",
  "下装",
  "连衣裙",
  "外套",
  "鞋子",
  "包袋",
  "妆容",
  "场景"
];

const ONE_PIECE_CATEGORIES: readonly ComboCategory[] = ["连衣裙"];

/** 「件 / 条 / 双」——提示语里用对量词，读起来才像人写的。 */
const MEASURE_WORDS: Partial<Record<ComboCategory, string>> = {
  鞋子: "双",
  下装: "条",
  连衣裙: "条"
};

function countByCategory(items: readonly ComboRuleItem[]): Map<ComboCategory, number> {
  const counts = new Map<ComboCategory, number>();
  items.forEach((item) => {
    counts.set(item.category, (counts.get(item.category) ?? 0) + 1);
  });
  return counts;
}

export function auditCombo(items: readonly ComboRuleItem[]): ComboAudit {
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
