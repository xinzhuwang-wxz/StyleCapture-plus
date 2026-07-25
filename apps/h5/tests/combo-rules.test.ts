import { describe, expect, it } from "vitest";

import { auditCombo } from "../src/features/wardrobe/comboRules";
import { CATALOG_ITEMS, type CatalogItem } from "../src/features/wardrobe/catalog";

function pick(...ids: string[]): CatalogItem[] {
  return ids.map((id) => {
    const item = CATALOG_ITEMS.find((entry) => entry.id === id);
    if (!item) throw new Error(`unknown catalog item ${id}`);
    return item;
  });
}

/**
 * Issue #4：「硬规则在生成式重排前执行，能阻止连衣裙与上衣/下装冲突」。
 * 这些规则是确定性的，不交给模型判断。
 */
describe("自由组合的品类硬规则", () => {
  it("少于两件时拒绝保存", () => {
    expect(auditCombo(pick("item-top-1"))).toEqual({
      ok: false,
      reason: "至少选 2 件才能搭一套哦"
    });
  });

  it("放行一套结构完整的搭配", () => {
    expect(auditCombo(pick("item-top-1", "item-bottom-1", "item-shoe-1"))).toEqual({
      ok: true
    });
  });

  it("挡下重复的上装并说明原因", () => {
    expect(auditCombo(pick("item-top-1", "item-top-3"))).toEqual({
      ok: false,
      reason: "选了 2 件上装"
    });
  });

  it("鞋子用「双」作量词", () => {
    expect(auditCombo(pick("item-shoe-1", "item-shoe-2"))).toEqual({
      ok: false,
      reason: "选了 2 双鞋子"
    });
  });

  it("挡下连衣裙与上下装同时出现", () => {
    expect(auditCombo(pick("item-dress-1", "item-top-1"))).toEqual({
      ok: false,
      reason: "连衣裙和上下装冲突了"
    });
    expect(auditCombo(pick("item-dress-1", "item-bottom-1"))).toEqual({
      ok: false,
      reason: "连衣裙和上下装冲突了"
    });
  });

  it("连衣裙搭配鞋子与配饰是允许的", () => {
    expect(auditCombo(pick("item-dress-1", "item-shoe-2", "item-acc-1"))).toEqual({
      ok: true
    });
  });

  it("多件配饰不算重复", () => {
    expect(auditCombo(pick("item-dress-1", "item-acc-1", "item-acc-2"))).toEqual({
      ok: true
    });
  });
});
