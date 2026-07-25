import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { CommunityScreen } from "../src/features/community/CommunityScreen";

describe("CommunityScreen", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lets a mobile user move, react, inspect a labelled resident, and prepare a share card", async () => {
    const user = userEvent.setup();
    const download = vi.fn();
    const drawImage = vi.fn();
    vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue("data:image/png;base64,card");
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(download);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      fillStyle: "",
      font: "",
      fillRect: vi.fn(),
      fillText: vi.fn(),
      drawImage
    } as unknown as CanvasRenderingContext2D);

    render(<CommunityScreen />);

    expect(screen.getByRole("heading", { name: "今晚舞会" })).toBeInTheDocument();
    expect(screen.getByText(/Demo 像素形象/)).toBeInTheDocument();
    const map = screen.getByRole("region", { name: "像素舞池地图" });
    expect(map).toBeInTheDocument();

    map.focus();
    fireEvent.keyDown(map, { key: "ArrowRight" });
    expect(screen.getByRole("status")).toHaveTextContent("已走到新的位置");

    await user.click(screen.getByRole("button", { name: "向右移动" }));
    await user.click(screen.getByRole("button", { name: "闪闪" }));
    expect(screen.getByRole("status")).toHaveTextContent("发送了 ✦");

    const residentButton = screen.getByRole("button", { name: "查看紫丁香的公开穿搭" });
    await user.click(residentButton);
    const dialog = screen.getByRole("dialog", { name: "紫丁香的公开穿搭" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveTextContent(
      "场景居民"
    );
    expect(screen.getByRole("button", { name: "关闭紫丁香的公开穿搭" })).toHaveFocus();

    const drawCountBeforeShare = drawImage.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "生成分享卡" }));
    expect(download).toHaveBeenCalledTimes(1);
    expect(drawImage).toHaveBeenCalledTimes(drawCountBeforeShare + 1);
    expect(screen.getByRole("status")).toHaveTextContent("分享卡已准备好");

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(residentButton).toHaveFocus());
  });

  it("sends the user to a pixel-only runway with applause and a return control", async () => {
    const user = userEvent.setup();
    const { container } = render(<CommunityScreen />);

    await user.click(screen.getByRole("button", { name: "轮到我上台" }));

    expect(screen.getByRole("status")).toHaveTextContent("正在走秀");
    expect(screen.getByText("喝彩 12")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "像素观众" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "走秀看板" })).toHaveTextContent("Demo 像素形象");
    expect(screen.getByRole("button", { name: "回到后台" })).toBeInTheDocument();
    expect(container.querySelector(".scene-avatar img")).not.toBeInTheDocument();
  });

  it("draws the current runway applause and reaction onto the share card", async () => {
    const user = userEvent.setup();
    const download = vi.fn();
    const drawImage = vi.fn();
    const fillText = vi.fn();
    vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue("data:image/png;base64,card");
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(download);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      fillStyle: "",
      font: "",
      fillRect: vi.fn(),
      fillText,
      drawImage
    } as unknown as CanvasRenderingContext2D);

    render(<CommunityScreen />);

    await user.click(screen.getByRole("button", { name: "闪闪" }));
    await user.click(screen.getByRole("button", { name: "轮到我上台" }));
    await user.click(screen.getByRole("button", { name: "生成分享卡" }));

    expect(download).toHaveBeenCalledTimes(1);
    expect(drawImage).toHaveBeenCalled();
    expect(fillText).toHaveBeenCalledWith("正在走秀 · 喝彩 12", 64, 918);
    expect(fillText).toHaveBeenCalledWith("✦ Demo 像素形象 · #StyleCapture", 64, 952);
    expect(screen.getByRole("status")).toHaveTextContent("分享卡已准备好");
  });
});
