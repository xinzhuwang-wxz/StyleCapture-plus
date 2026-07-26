import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { CommunityScreen } from "../src/features/community/CommunityScreen";

/** The rail is the wardrobe; the detail panel has its own "换上这套" button. */
function railButtons() {
  return within(screen.getByLabelText("我今晚的 Look")).getAllByRole("button", {
    name: /^换上/
  });
}

function railButton(name: string) {
  return within(screen.getByLabelText("我今晚的 Look")).getByRole("button", {
    name
  });
}

describe("CommunityScreen", () => {
  afterEach(() => vi.restoreAllMocks());

  it("opens as a labelled pixel world with a wardrobe and no fabricated community", async () => {
    render(<CommunityScreen />);

    expect(
      screen.getByLabelText(
        "花房夜宴像素世界，点击地面走动，点击角色查看他的 Look"
      )
    ).toBeInTheDocument();
    expect(screen.getByText(/预设角色非真人 · 非实时社区/)).toBeInTheDocument();
    expect(
      screen.getByText("只记录本次体验，不展示虚构点赞数。")
    ).toBeInTheDocument();

    // The catalogue is browsable as outfits, and one is currently worn.
    const worn = railButtons().filter(
      (button) => button.getAttribute("aria-pressed") === "true"
    );
    expect(worn).toHaveLength(1);
  });

  it("changes the whole outfit from the rail without leaving the party", async () => {
    const user = userEvent.setup();
    render(<CommunityScreen />);

    await user.click(railButton("换上薄荷花园"));

    expect(screen.getByRole("status")).toHaveTextContent("已换上：薄荷花园");
    expect(railButton("换上薄荷花园")).toHaveAttribute("aria-pressed", "true");
  });

  it("publishes the worn Look only when the user walks the runway", async () => {
    const user = userEvent.setup();
    const onPublishLook = vi.fn();
    render(<CommunityScreen onPublishLook={onPublishLook} />);

    expect(onPublishLook).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "上台走秀" }));

    expect(onPublishLook).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("status")).toHaveTextContent("走秀开始");
  });

  it("keeps an uploaded Look in the wardrobe until the user puts it on", async () => {
    const user = userEvent.setup();
    render(<CommunityScreen />);

    const before = railButtons().length;
    fireEvent.change(screen.getByLabelText("上传我的像素 Look"), {
      target: {
        files: [new File(["x"], "look.png", { type: "image/png" })]
      }
    });

    expect(screen.getByRole("status")).toHaveTextContent("已加入衣橱");
    expect(railButtons()).toHaveLength(before + 1);
    // Added, but not yet worn.
    expect(railButton("换上look.png")).toHaveAttribute(
      "aria-pressed",
      "false"
    );

    await user.click(railButton("换上look.png"));
    expect(railButton("换上look.png")).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("rejects a non-image instead of replacing the current Look", () => {
    render(<CommunityScreen />);
    const before = railButtons().length;

    fireEvent.change(screen.getByLabelText("上传我的像素 Look"), {
      target: {
        files: [
          new File(["not-an-image"], "look.pdf", { type: "application/pdf" })
        ]
      }
    });

    expect(screen.getByRole("status")).toHaveTextContent(
      "请选择 JPG、PNG、WebP 或 HEIC 图片"
    );
    expect(railButtons()).toHaveLength(before);
  });

  it("switches location and reports where the party moved to", async () => {
    const user = userEvent.setup();
    render(<CommunityScreen />);

    await user.click(screen.getByRole("button", { name: "天台花园" }));

    expect(screen.getByRole("button", { name: "天台花园" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    // The status names the occasion, so it is clear what kind of gathering it is.
    expect(screen.getByRole("status")).toHaveTextContent("黄昏天台派对");
  });

  it("collects a curated Look and records a single style reaction", async () => {
    const user = userEvent.setup();
    const onSaveInspiration = vi.fn();
    const onReaction = vi.fn();
    render(
      <CommunityScreen
        onSaveInspiration={onSaveInspiration}
        onReaction={onReaction}
      />
    );

    await user.click(screen.getByRole("button", { name: "收藏灵感" }));
    expect(onSaveInspiration).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("status")).toHaveTextContent("已收藏");

    await user.click(screen.getByRole("button", { name: "层次感" }));
    expect(onReaction).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "层次感" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("exports the group card and reports success", async () => {
    const user = userEvent.setup();
    const download = vi.fn();
    const onShare = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(download);

    render(<CommunityScreen onShare={onShare} />);
    // The shutter freezes the frame, then offers the two formats.
    await user.click(screen.getByRole("button", { name: "拍合影" }));
    await user.click(screen.getByRole("button", { name: "静态合影卡" }));

    await waitFor(
      () => expect(screen.getByRole("status")).toHaveTextContent("同框合影已保存"),
      { timeout: 12000 }
    );
    expect(download).toHaveBeenCalledTimes(1);
    expect(onShare).toHaveBeenCalledTimes(1);
  }, 20000);

  it("shows a retry state when the card cannot be drawn instead of reporting success", async () => {
    const user = userEvent.setup();
    const download = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(download);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);

    render(<CommunityScreen />);
    await user.click(screen.getByRole("button", { name: "拍合影" }));
    await user.click(screen.getByRole("button", { name: "静态合影卡" }));

    await waitFor(
      () =>
        expect(screen.getByRole("status")).toHaveTextContent("合影生成失败，请重试"),
      { timeout: 12000 }
    );
    expect(screen.getByRole("alert")).toHaveTextContent("生成失败，请重试");
    expect(download).not.toHaveBeenCalled();
  }, 20000);

  it("speaks as the player and shows it as a bubble in the world", async () => {
    const user = userEvent.setup();
    render(<CommunityScreen />);

    const input = screen.getByLabelText("说一句话");
    const send = screen.getByRole("button", { name: "说" });
    expect(send).toBeDisabled();

    await user.type(input, "大家好呀");
    expect(send).toBeEnabled();
    await user.click(send);

    expect(screen.getByRole("status")).toHaveTextContent("你说：大家好呀");
    // The composer clears so the next line can be typed straight away.
    expect(input).toHaveValue("");
  });

  it("no longer offers the dance button that did nothing", () => {
    render(<CommunityScreen />);
    expect(
      screen.queryByRole("button", { name: "加入舞会" })
    ).not.toBeInTheDocument();
  });

  it("keeps photo options behind the shutter so the dock stays small", async () => {
    const user = userEvent.setup();
    render(<CommunityScreen />);

    expect(
      screen.queryByRole("button", { name: "静态合影卡" })
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "拍合影" }));
    expect(screen.getByRole("button", { name: "拍合影" })).toHaveAttribute(
      "aria-expanded",
      "true"
    );
    expect(screen.getByRole("status")).toHaveTextContent("画面已定格");
    expect(
      screen.getByRole("button", { name: /合影动图/ })
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "继续舞会" }));
    expect(
      screen.queryByRole("button", { name: "静态合影卡" })
    ).not.toBeInTheDocument();
  });

  it("enters layout-only fullscreen immediately even when the native API stalls", async () => {
    const user = userEvent.setup();
    const stalled = new Promise<void>(() => undefined);
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: vi.fn(() => stalled)
    });
    render(<CommunityScreen />);

    await user.click(screen.getByRole("button", { name: "进入全屏世界" }));

    expect(screen.getByRole("button", { name: "退出全屏世界" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByRole("status")).toHaveTextContent("已进入全屏世界");
    delete (HTMLElement.prototype as Partial<HTMLElement>).requestFullscreen;
  });

  it("keeps the H5 layout immersive when the browser drops native fullscreen", async () => {
    const user = userEvent.setup();
    Object.defineProperty(HTMLElement.prototype, "requestFullscreen", {
      configurable: true,
      value: vi.fn(async () => undefined)
    });
    render(<CommunityScreen />);

    await user.click(screen.getByRole("button", { name: "进入全屏世界" }));
    document.dispatchEvent(new Event("fullscreenchange"));

    expect(screen.getByRole("button", { name: "退出全屏世界" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByRole("status")).toHaveTextContent("已进入全屏世界");
    delete (HTMLElement.prototype as Partial<HTMLElement>).requestFullscreen;
  });

  it("wears a supplied public render artifact and publishes that same Look", async () => {
    const user = userEvent.setup();
    const onPublishLook = vi.fn();

    render(
      <CommunityScreen
        onPublishLook={onPublishLook}
        avatarSource={{
          assetUrl: "/assets/public-look.png",
          label: "我的公开 Look",
          kind: "public-render-artifact"
        }}
      />
    );

    expect(railButton("换上我的公开 Look")).toHaveAttribute(
      "aria-pressed",
      "true"
    );

    await user.click(screen.getByRole("button", { name: "上台走秀" }));

    expect(onPublishLook).toHaveBeenCalledWith(
      expect.objectContaining({ assetUrl: "/assets/public-look.png" })
    );
  });
});
