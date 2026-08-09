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
  it("shows a focused pixel-cover share sheet", () => {
    renderSheet();
    expect(
      screen.getByRole("img", { name: "暖棕复古的像素图鉴" })
    ).toHaveAttribute("src", "/v1/looks/a/renders/pixel.png");
    expect(screen.getByRole("heading", { name: "✦ 分享像素封面 ✦" })).toBeInTheDocument();
  });

  it("hands sharing to the system rather than claiming to post anywhere", async () => {
    const user = userEvent.setup();
    const props = renderSheet();
    // The H5 still opens the system share surface; it never claims to publish
    // content automatically on the user's behalf.
    const share = screen.getByRole("button", { name: "分享到抖音" });
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

  it("replaces the image with a busy state while preparing", () => {
    renderSheet({ sharing: true });
    expect(screen.getByRole("status")).toHaveTextContent("正在准备图片…");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "分享到抖音" })).toBeDisabled();
  });

  it("says what the card does and does not contain", () => {
    renderSheet();
    expect(screen.getByText(/不包含原始穿搭照片/)).toBeInTheDocument();
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
      const dialog = screen.getByRole("dialog", { name: "分享像素封面" });
      expect(screen_.contains(dialog)).toBe(true);
    } finally {
      screen_.remove();
    }
  });
});
