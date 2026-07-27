import type { Item } from "../src/api/client";
import {
  MAX_BASKET_ITEMS,
  addToBasket,
  auditBasket,
  basketEntryOf,
  comboCategoryOf,
  isInBasket,
  removeFromBasket,
  type BasketEntry
} from "../src/features/combo/basketRules";

function item(id: string, categorySlug: string): Item {
  return {
    id,
    attributes: { category: { value: categorySlug } },
    display_image_url: `/v1/items/${id}/image`
  } as unknown as Item;
}

function entry(id: string, slug: string, label = id): BasketEntry {
  return basketEntryOf(item(id, slug), label);
}

describe("combo basket", () => {
  it("maps the backend's category slugs onto the existing rule vocabulary", () => {
    expect(comboCategoryOf(item("a", "tops"))).toBe("上装");
    expect(comboCategoryOf(item("a", "bottoms"))).toBe("下装");
    expect(comboCategoryOf(item("a", "dresses"))).toBe("连衣裙");
    expect(comboCategoryOf(item("a", "outerwear"))).toBe("外套");
    expect(comboCategoryOf(item("a", "shoes"))).toBe("鞋子");
    expect(comboCategoryOf(item("a", "bags"))).toBe("包袋");
    // Headwear and accessories behave the same way when styling an outfit.
    expect(comboCategoryOf(item("a", "headwear"))).toBe("配饰");
    expect(comboCategoryOf(item("a", "accessories"))).toBe("配饰");
  });

  it("returns null for a category it does not recognise rather than guessing", () => {
    expect(comboCategoryOf(item("a", "spacesuit"))).toBeNull();
    expect(comboCategoryOf({ id: "a", attributes: {} } as unknown as Item)).toBeNull();
  });

  it("adds an item once and reports membership", () => {
    let basket: readonly BasketEntry[] = [];
    basket = addToBasket(basket, entry("a", "tops"));
    basket = addToBasket(basket, entry("a", "tops"));
    expect(basket).toHaveLength(1);
    expect(isInBasket(basket, "a")).toBe(true);
    expect(isInBasket(basket, "b")).toBe(false);
  });

  it("stops at the cap instead of growing without bound", () => {
    let basket: readonly BasketEntry[] = [];
    for (let index = 0; index < MAX_BASKET_ITEMS + 3; index += 1) {
      basket = addToBasket(basket, entry(`i${index}`, "accessories"));
    }
    expect(basket).toHaveLength(MAX_BASKET_ITEMS);
  });

  it("removes an item", () => {
    const basket = addToBasket(
      addToBasket([], entry("a", "tops")),
      entry("b", "shoes")
    );
    expect(removeFromBasket(basket, "a").map((e) => e.itemId)).toEqual(["b"]);
  });

  it("delegates the duplicate-category rule to the existing wardrobe rules", () => {
    // Two tops is exactly what comboRules already rejects; do not re-implement.
    const twoTops = [entry("a", "tops"), entry("b", "tops")];
    const audit = auditBasket(twoTops);
    expect(audit.ok).toBe(false);
    if (!audit.ok) expect(audit.reason).toContain("上装");
  });

  it("rejects a dress worn with separates", () => {
    const audit = auditBasket([entry("a", "dresses"), entry("b", "bottoms")]);
    expect(audit.ok).toBe(false);
    if (!audit.ok) expect(audit.reason).toContain("连衣裙");
  });

  it("accepts a sensible outfit", () => {
    expect(
      auditBasket([entry("a", "tops"), entry("b", "bottoms"), entry("c", "shoes")])
    ).toEqual({ ok: true });
  });

  it("asks for a second piece before it will call anything an outfit", () => {
    const audit = auditBasket([entry("a", "tops")]);
    expect(audit.ok).toBe(false);
    if (!audit.ok) expect(audit.reason).toContain("2 件");
  });

  it("does not fail an outfit just because one item's category is unknown", () => {
    // An unrecognised category could be anything; inventing a rule for it
    // would produce a false rejection the user cannot act on.
    const audit = auditBasket([
      entry("a", "spacesuit"),
      entry("b", "tops"),
      entry("c", "bottoms")
    ]);
    expect(audit).toEqual({ ok: true });
  });
});
