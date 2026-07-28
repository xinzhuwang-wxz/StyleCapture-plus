import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ShareCardSheet } from "../src/features/outfit/ShareCardSheet";

function renderSheet(overrides: Partial<Parameters<typeof ShareCardSheet>[0]> = {}) {
  const props = {
    imageUrl: "/v1/looks/a/renders/pixel.png",
    title: "暖棕复古",
    onShare: vi.fn(),
    onSave: vi.fn(),
    onClose: vi.fn(),
    ...overrides
  };
  render(<ShareCardSheet {...props} />);
  return props;
}

describe("share card sheet", () => {
  it("shows the cover with the account tag", () => {
    renderSheet();
    expect(
      screen.getByRole("img", { name: "暖棕复古的像素图鉴" })
    ).toHaveAttribute("src", "/v1/looks/a/renders/pixel.png");
    expect(screen.getByText("@码上搭 · 我的数字衣橱")).toBeInTheDocument();
  });

  it("hands sharing to the system rather than claiming to post anywhere", async () => {
    const user = userEvent.setup();
    const props = renderSheet();
    // An H5 cannot publish to Douyin on the user's behalf; the honest offer is
    // the system share sheet, so the label must not promise a one-tap post.
    const share = screen.getByRole("button", { name: "分享到…" });
    expect(screen.queryByText(/一键发/)).not.toBeInTheDocument();
    await user.click(share);
    expect(props.onShare).toHaveBeenCalledTimes(1);
  });

  it("saves the image through the caller's existing download path", async () => {
    const user = userEvent.setup();
    const props = renderSheet();
    await user.click(screen.getByRole("button", { name: "保存到相册" }));
    expect(props.onSave).toHaveBeenCalledTimes(1);
  });

  it("copies a real link instead of drawing a fake QR code", async () => {
    // userEvent.setup() installs its own clipboard stub, so ours has to go in
    // afterwards or it gets replaced.
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText }
    });
    renderSheet();
    await user.click(screen.getByRole("button", { name: "复制链接看同款" }));
    expect(writeText).toHaveBeenCalledWith(window.location.href);
    expect(await screen.findByText(/链接已复制/)).toBeInTheDocument();
  });

  it("admits it when the device refuses to copy", async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: vi.fn().mockRejectedValue(new Error("denied"))
      }
    });
    renderSheet();
    await user.click(screen.getByRole("button", { name: "复制链接看同款" }));
    expect(await screen.findByText(/不让自动复制/)).toBeInTheDocument();
  });

  it("replaces the image with a busy state while preparing", () => {
    renderSheet({ sharing: true });
    expect(screen.getByRole("status")).toHaveTextContent("正在准备图片…");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "分享到…" })).toBeDisabled();
  });

  it("says what the card does and does not contain", () => {
    renderSheet();
    expect(screen.getByText(/不含原始穿搭照片/)).toBeInTheDocument();
  });

  it("closes", async () => {
    const user = userEvent.setup();
    const props = renderSheet();
    await user.click(screen.getByRole("button", { name: "关闭" }));
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("floats above the whole screen instead of sitting inside the page flow", () => {
    // 弹层是 absolute，原地渲染时定位祖先在详情页的滚动内容里，结果落到卡片
    // 下方还跟着滚。挂到 .pixel-screen 上才是真的浮层。
    const screen_ = document.createElement("div");
    screen_.className = "pixel-screen";
    document.body.appendChild(screen_);
    try {
      renderSheet();
      const dialog = screen.getByRole("dialog", { name: "分享图鉴" });
      expect(screen_.contains(dialog)).toBe(true);
    } finally {
      screen_.remove();
    }
  });
});
