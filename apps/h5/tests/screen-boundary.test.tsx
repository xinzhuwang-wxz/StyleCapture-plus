import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ScreenBoundary } from "../src/components/ScreenBoundary";

function Boom(): JSX.Element {
  throw new Error("Failed to fetch dynamically imported module");
}

describe("screen boundary", () => {
  const reload = vi.fn();
  let consoleError: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    reload.mockClear();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, reload }
    });
    // React 会把边界捕获到的错误再打一遍，测试输出里那一大段不是失败。
    consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => consoleError.mockRestore());

  it("passes children through when nothing is wrong", () => {
    render(
      <ScreenBoundary>
        <p>衣橱</p>
      </ScreenBoundary>
    );
    expect(screen.getByText("衣橱")).toBeInTheDocument();
  });

  it("offers a way back instead of leaving a blank page", () => {
    render(
      <ScreenBoundary>
        <Boom />
      </ScreenBoundary>
    );
    // 懒加载分块取不到会一路冒到根节点，整页变白。真机上遇到过。
    expect(screen.getByRole("alert")).toHaveTextContent("没能加载出来");
    expect(screen.getByRole("button", { name: "重新加载" })).toBeInTheDocument();
  });

  it("clears the restored detail first, or the reload just crashes again", async () => {
    const user = userEvent.setup();
    window.sessionStorage.setItem("stylecapture:selected-look:v1", "look-1");
    render(
      <ScreenBoundary>
        <Boom />
      </ScreenBoundary>
    );

    await user.click(screen.getByRole("button", { name: "重新加载" }));
    // 上次打开的详情会被恢复出来重走同一条路——这正是「刷新也没用」的原因。
    expect(
      window.sessionStorage.getItem("stylecapture:selected-look:v1")
    ).toBeNull();
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
