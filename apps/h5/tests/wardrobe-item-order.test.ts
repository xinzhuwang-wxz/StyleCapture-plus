import type { Item } from "../src/api/client";
import { orderItemsNewestFirst } from "../src/features/wardrobe/WardrobeScreen";

function item(id: string, createdAt: string): Item {
  return { id, created_at: createdAt } as Item;
}

describe("wardrobe item order", () => {
  it("shows newly added items before older items without mutating the API result", () => {
    const older = item("older", "2026-08-08T08:00:00Z");
    const newest = item("newest", "2026-08-10T08:00:00Z");
    const middle = item("middle", "2026-08-09T08:00:00Z");
    const apiItems = [older, newest, middle];

    expect(orderItemsNewestFirst(apiItems).map(({ id }) => id)).toEqual([
      "newest",
      "middle",
      "older"
    ]);
    expect(apiItems.map(({ id }) => id)).toEqual(["older", "newest", "middle"]);
  });
});
