import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { wardrobeApi, type Item } from "../src/api/client";
import { ItemDetail } from "../src/features/wardrobe/ItemDetail";
import {
  LookItemActionSheet,
  type LookItemAction
} from "../src/features/wardrobe/LookItemActionSheet";

vi.mock("../src/features/wardrobe/useDisplayImage", () => ({
  useDisplayImage: () => "/v1/items/item-owned/image"
}));

beforeEach(() => {
  vi.spyOn(wardrobeApi, "ensureItemFlatLayPresentation").mockRejectedValue(
    new Error("测试中暂不生成")
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

const item: Item = {
  id: "item-owned",
  capture_id: "capture-owned",
  status: "ready",
  ownership: "owned",
  source_kind: "upload",
  display_image_url: "/v1/items/item-owned/image",
  display_image_kind: "derived_garment",
  source_image_url: "/v1/items/item-owned/source",
  source_available: true,
  purchase_search_query: "蓝黄印花吊带连衣裙",
  purchase_search_url:
    "https://www.douyin.com/search/%E8%93%9D%E9%BB%84%E5%8D%B0%E8%8A%B1%E5%90%8A%E5%B8%A6%E8%BF%9E%E8%A1%A3%E8%A3%99",
  attributes: {
    category: {
      value: "dresses",
      provenance: "model",
      confidence: 0.92,
      model_version: "test-model",
      locked: false
    },
    description: {
      value: "蓝黄印花吊带连衣裙",
      provenance: "model",
      confidence: 0.92,
      model_version: "test-model",
      locked: false
    }
  },
  model_metadata: {},
  created_at: "2026-08-08T00:00:00Z",
  updated_at: "2026-08-08T00:00:00Z"
};

describe("Item detail actions", () => {
  it("autosaves ownership and keeps the shopping shortcut beside outfit building", async () => {
    const onSave = vi.fn();
    render(
      <ItemDetail
        item={item}
        saving={false}
        onClose={vi.fn()}
        onSave={onSave}
        onDeleteSource={vi.fn()}
        onBuildOutfit={vi.fn()}
        onReturnToFeed={vi.fn()}
      />
    );

    expect(await screen.findByText("单品图已生成")).toBeVisible();

    expect(screen.getByText("相册录入")).toBeInTheDocument();
    expect(screen.queryByText("单品描述")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "保存修改" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "待拥有" }));
    expect(onSave).toHaveBeenCalledWith("item-owned", {
      ownership: "inspiration"
    });
    expect(
      screen.getByRole("link", { name: "去抖音商城搜索蓝黄印花吊带连衣裙" })
    ).toHaveAttribute("href", item.purchase_search_url);
  });

  it("keeps a usable Douyin link while an older backend is still rolling out", async () => {
    render(
      <ItemDetail
        item={{
          ...item,
          purchase_search_query: "",
          purchase_search_url: ""
        }}
        saving={false}
        onClose={vi.fn()}
        onSave={vi.fn()}
        onDeleteSource={vi.fn()}
        onBuildOutfit={vi.fn()}
        onReturnToFeed={vi.fn()}
      />
    );

    expect(await screen.findByText("单品图已生成")).toBeVisible();

    expect(
      screen.getByRole("link", { name: "去抖音商城搜索蓝黄印花吊带连衣裙" })
    ).toHaveAttribute(
      "href",
      "https://www.douyin.com/search/%E8%93%9D%E9%BB%84%E5%8D%B0%E8%8A%B1%E5%90%8A%E5%B8%A6%E8%BF%9E%E8%A1%A3%E8%A3%99"
    );
  });
});

describe("Look item action sheet", () => {
  function renderSheet(action: LookItemAction) {
    const onBuildOutfit = vi.fn();
    const onCheckCompatibility = vi.fn();
    render(
      <LookItemActionSheet
        action={action}
        onClose={vi.fn()}
        onBuildOutfit={onBuildOutfit}
        onCheckCompatibility={onCheckCompatibility}
      />
    );
    return { onBuildOutfit, onCheckCompatibility };
  }

  it("offers a single compose action for a backend-owned item", () => {
    const { onBuildOutfit } = renderSheet({
      itemId: item.id,
      label: "连衣裙",
      imageUrl: item.display_image_url,
      ownership: "owned",
      purchaseSearchUrl: item.purchase_search_url
    });

    fireEvent.click(screen.getByRole("button", { name: "已拥有，去搭配" }));
    expect(onBuildOutfit).toHaveBeenCalledWith(item.id);
    expect(screen.queryByText("未拥有，去购买")).not.toBeInTheDocument();
  });

  it("offers shopping and temporary AI compatibility actions for an unowned item", () => {
    const { onCheckCompatibility } = renderSheet({
      itemId: item.id,
      label: "连衣裙",
      imageUrl: item.display_image_url,
      ownership: "inspiration",
      purchaseSearchUrl: item.purchase_search_url
    });

    expect(screen.getByRole("link", { name: "未拥有，去购买" })).toHaveAttribute(
      "href",
      item.purchase_search_url
    );
    fireEvent.click(
      screen.getByRole("button", { name: "检测与已有穿搭的适配度" })
    );
    expect(onCheckCompatibility).toHaveBeenCalledWith(item.id);
  });

  it("falls back to a keyword search instead of disabling purchase", () => {
    renderSheet({
      itemId: item.id,
      label: "蓝黄印花吊带连衣裙",
      imageUrl: item.display_image_url,
      ownership: "inspiration",
      purchaseSearchUrl: null
    });

    expect(screen.queryByText("暂无购买链接")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "未拥有，去购买" })).toHaveAttribute(
      "href",
      "https://www.douyin.com/search/%E8%93%9D%E9%BB%84%E5%8D%B0%E8%8A%B1%E5%90%8A%E5%B8%A6%E8%BF%9E%E8%A1%A3%E8%A3%99"
    );
  });

  it("restores focus without scrolling the phone screen", async () => {
    const phoneScreen = document.createElement("div");
    const trigger = document.createElement("button");
    phoneScreen.append(trigger);
    document.body.append(phoneScreen);
    phoneScreen.scrollTop = 37;
    trigger.focus();
    const triggerFocus = vi.spyOn(trigger, "focus");
    const action: LookItemAction = {
      itemId: item.id,
      label: "连衣裙",
      imageUrl: item.display_image_url,
      ownership: "owned",
      purchaseSearchUrl: item.purchase_search_url
    };
    const props = {
      onClose: vi.fn(),
      onBuildOutfit: vi.fn(),
      onCheckCompatibility: vi.fn()
    };
    const { rerender } = render(
      <LookItemActionSheet action={action} {...props} />
    );

    phoneScreen.scrollTop = 180;
    rerender(<LookItemActionSheet action={null} {...props} />);

    await waitFor(() => {
      expect(triggerFocus).toHaveBeenCalledWith({ preventScroll: true });
      expect(phoneScreen.scrollTop).toBe(37);
    });
    phoneScreen.remove();
  });
});
