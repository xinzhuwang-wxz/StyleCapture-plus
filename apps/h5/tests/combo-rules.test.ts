import { describe, expect, it } from "vitest";

import {
  auditCombo,
  type ComboCategory,
  type ComboRuleItem
} from "../src/features/wardrobe/comboRules";

function pick(...categories: ComboCategory[]): ComboRuleItem[] {
  return categories.map((category) => ({ category }));
}

describe("自由组合的品类硬规则", () => {
  it("少于两件时拒绝保存", () => {
    expect(auditCombo(pick("上装"))).toEqual({
      ok: false,
      reason: "至少选 2 件才能搭一套哦"
    });
  });

  it("放行一套结构完整的搭配", () => {
    expect(auditCombo(pick("上装", "下装", "鞋子"))).toEqual({
      ok: true
    });
  });

  it("挡下重复的上装并说明原因", () => {
    expect(auditCombo(pick("上装", "上装"))).toEqual({
      ok: false,
      reason: "选了 2 件上装"
    });
  });

  it("鞋子用「双」作量词", () => {
    expect(auditCombo(pick("鞋子", "鞋子"))).toEqual({
      ok: false,
      reason: "选了 2 双鞋子"
    });
  });

  it("挡下连衣裙与上下装同时出现", () => {
    expect(auditCombo(pick("连衣裙", "上装"))).toEqual({
      ok: false,
      reason: "连衣裙和上下装冲突了"
    });
    expect(auditCombo(pick("连衣裙", "下装"))).toEqual({
      ok: false,
      reason: "连衣裙和上下装冲突了"
    });
  });

  it("连衣裙搭配鞋子与配饰是允许的", () => {
    expect(auditCombo(pick("连衣裙", "鞋子", "配饰"))).toEqual({
      ok: true
    });
  });

  it("多件配饰不算重复", () => {
    expect(auditCombo(pick("连衣裙", "配饰", "配饰"))).toEqual({
      ok: true
    });
  });
});
