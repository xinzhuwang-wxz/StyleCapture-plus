import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { CommunityScreen } from "../src/features/community/CommunityScreen";

function markImageReady(width = 1086, height = 1448) {
  Object.defineProperty(HTMLImageElement.prototype, "complete", {
    configurable: true,
    value: true
  });
  Object.defineProperty(HTMLImageElement.prototype, "naturalWidth", {
    configurable: true,
    value: width
  });
  Object.defineProperty(HTMLImageElement.prototype, "naturalHeight", {
    configurable: true,
    value: height
  });
}

describe("CommunityScreen", () => {
  afterEach(() => vi.restoreAllMocks());

  it("presents a purposeful theme room and lets the user browse, collect, enter, and react", async () => {
    const user = userEvent.setup();
    render(<CommunityScreen />);

    expect(
      screen.getByRole("heading", { name: "花房晚宴" })
    ).toBeInTheDocument();
    expect(screen.getByText("主题陈列室 Demo · 非实时社区")).toBeInTheDocument();
    expect(screen.getAllByText("精选示例 · 非真人").length).toBeGreaterThan(0);
    expect(screen.getByRole("img", { name: "暖棕复古 Look 像素形象" })).toHaveAttribute(
      "src",
      "/assets/community/pixel-look-1.png"
    );

    await user.click(screen.getByRole("button", { name: /查看薄荷花园/ }));
    expect(
      screen.getAllByRole("heading", { name: "薄荷花园" })
    ).toHaveLength(2);
    expect(screen.getAllByText(/轻柔层次/)).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "收藏这个搭配灵感" }));
    expect(screen.getByRole("status")).toHaveTextContent("已收藏：薄荷花园");

    await user.click(screen.getByRole("button", { name: "带我的 Look 登场" }));
    expect(screen.getByRole("status")).toHaveTextContent("你的 Look 已站上主题舞台");
    await waitFor(() =>
      expect(screen.getByRole("img", { name: "我的像素 Look" })).toHaveAttribute(
        "src",
        "/assets/char-default.png"
      )
    );

    await user.click(screen.getByRole("button", { name: "层次感" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "已记录：层次感 · 仅本次体验"
    );

  });

  it("waits for the selected pixel Look before exporting and prevents duplicate requests", async () => {
    const user = userEvent.setup();
    const download = vi.fn();
    const toDataURL = vi
      .spyOn(HTMLCanvasElement.prototype, "toDataURL")
      .mockReturnValue("data:image/png;base64,card");
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(download);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      fillStyle: "",
      font: "",
      textAlign: "left",
      fillRect: vi.fn(),
      fillText: vi.fn(),
      drawImage: vi.fn()
    } as unknown as CanvasRenderingContext2D);

    render(<CommunityScreen />);
    const selectedImage = screen.getByRole("img", {
      name: "暖棕复古 Look 像素形象"
    });
    Object.defineProperty(selectedImage, "complete", {
      configurable: true,
      value: false
    });
    Object.defineProperty(selectedImage, "naturalWidth", {
      configurable: true,
      value: 0
    });

    await user.click(screen.getByRole("button", { name: "生成像素分享卡" }));
    expect(screen.getByRole("button", { name: "正在准备分享卡…" })).toBeDisabled();
    expect(toDataURL).not.toHaveBeenCalled();

    Object.defineProperty(selectedImage, "naturalWidth", {
      configurable: true,
      value: 1086
    });
    Object.defineProperty(selectedImage, "naturalHeight", {
      configurable: true,
      value: 1448
    });
    fireEvent.load(selectedImage);

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("分享卡已准备好")
    );
    expect(download).toHaveBeenCalledTimes(1);
  });

  it("shows a retry state when Canvas is unavailable instead of reporting success", async () => {
    const user = userEvent.setup();
    markImageReady();
    const toDataURL = vi.spyOn(HTMLCanvasElement.prototype, "toDataURL");
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);

    render(<CommunityScreen />);
    await user.click(screen.getByRole("button", { name: "生成像素分享卡" }));

    expect(screen.getByRole("status")).toHaveTextContent(
      "分享卡生成失败，请重试"
    );
    expect(screen.getByRole("button", { name: "重试生成分享卡" })).toBeInTheDocument();
    expect(toDataURL).not.toHaveBeenCalled();
  });

  it("exports the supplied public RenderArtifact from the same visible image", async () => {
    const user = userEvent.setup();
    const drawImage = vi.fn();
    markImageReady(512, 512);
    vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue(
      "data:image/png;base64,card"
    );
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      fillStyle: "",
      font: "",
      textAlign: "left",
      fillRect: vi.fn(),
      fillText: vi.fn(),
      drawImage
    } as unknown as CanvasRenderingContext2D);

    render(
      <CommunityScreen
        avatarSource={{
          assetUrl: "/assets/public-look.png",
          label: "我的公开 Look",
          kind: "public-render-artifact"
        }}
      />
    );
    await user.click(screen.getByRole("button", { name: "带我的 Look 登场" }));
    await user.click(screen.getByRole("button", { name: "生成像素分享卡" }));

    await waitFor(() => expect(drawImage).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByRole("img", { name: "我的像素 Look" })).toHaveAttribute(
        "src",
        "/assets/public-look.png"
      )
    );
  });
});
