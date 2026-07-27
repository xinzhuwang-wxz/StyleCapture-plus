import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { Item } from "../src/api/client";
import { ComboDraggableItem } from "../src/features/combo/ComboDraggableItem";

function item(id = "i1"): Item {
  return {
    id,
    status: "ready",
    ownership: "owned",
    source_available: true,
    display_image_url: `/v1/items/${id}/image`,
    attributes: {
      category: { value: "tops" },
      description: { value: "象牙白绞花针织衫" }
    }
  } as unknown as Item;
}

function renderCard(overrides: Partial<Parameters<typeof ComboDraggableItem>[0]> = {}) {
  const props = {
    item: item(),
    inBasket: false,
    onOpen: vi.fn(),
    onRetry: vi.fn(),
    onRetryPixel: vi.fn(),
    onToggleBasket: vi.fn(),
    onDragActive: vi.fn(),
    ...overrides
  };
  render(<ComboDraggableItem {...props} />);
  return props;
}

describe("combo item card", () => {
  it("offers a plain button so the basket never depends on a drag gesture", async () => {
    const user = userEvent.setup();
    const props = renderCard();
    const add = screen.getByRole("button", { name: /加入组合衣柜/ });
    expect(add).toHaveAttribute("aria-pressed", "false");
    await user.click(add);
    // No subcategory on this item, so the basket label falls back to the category.
    expect(props.onToggleBasket).toHaveBeenCalledWith("上装");
  });

  it("does not open the item detail when the basket button is pressed", async () => {
    // The card wraps everything in pointer handlers; without a guard the press
    // would be read as a tap on the card and open the detail behind the sheet.
    const user = userEvent.setup();
    const props = renderCard();
    await user.click(screen.getByRole("button", { name: /加入组合衣柜/ }));
    expect(props.onOpen).not.toHaveBeenCalled();
  });

  it("still opens the detail on a normal tap of the card", async () => {
    const user = userEvent.setup();
    const props = renderCard();
    // Anchored so it matches the card opener, not the basket button that
    // also names the item.
    await user.click(screen.getByRole("button", { name: /^象牙白绞花针织衫/ }));
    expect(props.onOpen).toHaveBeenCalledTimes(1);
    expect(props.onToggleBasket).not.toHaveBeenCalled();
  });

  it("shows membership so the same button can take it back out", () => {
    renderCard({ inBasket: true });
    const button = screen.getByRole("button", { name: /移出组合衣柜/ });
    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(button).toHaveTextContent("已在组合");
  });

  it("leaves the retry action alone", async () => {
    const user = userEvent.setup();
    const props = renderCard({
      item: { ...item(), status: "error" } as unknown as Item
    });
    await user.click(screen.getByRole("button", { name: "重新识别" }));
    expect(props.onRetry).toHaveBeenCalledTimes(1);
    expect(props.onOpen).not.toHaveBeenCalled();
  });
});
