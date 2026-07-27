import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { BodyProfileSheet } from "../src/features/profile/BodyProfileSheet";
import {
  defaultBodyProfile,
  readBodyProfile
} from "../src/features/profile/profileStorage";

function memoryStorage(overrides: Partial<Storage> = {}): Storage {
  const map = new Map<string, string>();
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => void map.set(key, value),
    removeItem: (key) => void map.delete(key),
    clear: () => map.clear(),
    key: (index) => [...map.keys()][index] ?? null,
    get length() {
      return map.size;
    },
    ...overrides
  } as Storage;
}

function useStorage(store: Storage) {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: store
  });
}

beforeEach(() => useStorage(memoryStorage()));

function renderSheet(overrides: Partial<Parameters<typeof BodyProfileSheet>[0]> = {}) {
  const props = {
    profile: defaultBodyProfile(),
    onSaved: vi.fn(),
    onClose: vi.fn(),
    onNotice: vi.fn(),
    ...overrides
  };
  render(<BodyProfileSheet {...props} />);
  return props;
}

describe("body profile sheet", () => {
  it("exposes every metric as a keyboard-operable spinbutton", () => {
    renderSheet();
    const labels = ["年龄", "身高", "体重", "胸围", "腰围", "臀围"];
    labels.forEach((label) => {
      const wheel = screen.getByRole("spinbutton", { name: label });
      expect(wheel).toHaveAttribute("aria-valuenow");
      expect(wheel).toHaveAttribute("tabindex", "0");
    });
  });

  it("adjusts a metric with the keyboard, not only by dragging", async () => {
    const user = userEvent.setup();
    renderSheet();
    const height = screen.getByRole("spinbutton", { name: "身高" });
    const before = Number(height.getAttribute("aria-valuenow"));

    height.focus();
    await user.keyboard("{ArrowUp}");
    expect(Number(height.getAttribute("aria-valuenow"))).toBe(before + 1);

    await user.keyboard("{PageDown}");
    expect(Number(height.getAttribute("aria-valuenow"))).toBe(before - 4);
  });

  it("clamps at the declared range instead of running off", async () => {
    const user = userEvent.setup();
    renderSheet();
    const age = screen.getByRole("spinbutton", { name: "年龄" });
    age.focus();
    await user.keyboard("{Home}");
    expect(age).toHaveAttribute("aria-valuenow", "16");
    await user.keyboard("{ArrowDown}");
    expect(age).toHaveAttribute("aria-valuenow", "16");
    await user.keyboard("{End}");
    expect(age).toHaveAttribute("aria-valuenow", "45");
    await user.keyboard("{ArrowUp}");
    expect(age).toHaveAttribute("aria-valuenow", "45");
  });

  it("saves to this device and reports it, then closes", async () => {
    const user = userEvent.setup();
    const props = renderSheet();

    await user.clear(screen.getByLabelText("昵称"));
    await user.type(screen.getByLabelText("昵称"), "小甜甜");
    await user.click(
      within(screen.getByRole("group", { name: "身型" })).getByRole("button", {
        name: "沙漏形"
      })
    );
    await user.click(screen.getByRole("button", { name: "保存资料" }));

    expect(readBodyProfile()).toMatchObject({
      nickname: "小甜甜",
      shape: "沙漏形"
    });
    expect(props.onSaved).toHaveBeenCalledWith(
      expect.objectContaining({ nickname: "小甜甜", shape: "沙漏形" })
    );
    expect(props.onNotice).toHaveBeenCalledWith("身材资料已保存在本机");
    expect(props.onClose).toHaveBeenCalled();
  });

  it("refuses an empty nickname rather than saving a blank profile", async () => {
    const user = userEvent.setup();
    const props = renderSheet();

    await user.clear(screen.getByLabelText("昵称"));
    await user.click(screen.getByRole("button", { name: "保存资料" }));

    expect(screen.getByRole("alert")).toHaveTextContent("给自己起个昵称吧");
    expect(props.onSaved).not.toHaveBeenCalled();
    expect(props.onClose).not.toHaveBeenCalled();
  });

  it("says so when the device refuses to store, instead of claiming success", async () => {
    const quota = new Error("full");
    quota.name = "QuotaExceededError";
    useStorage(
      memoryStorage({
        setItem: () => {
          throw quota;
        }
      })
    );
    const user = userEvent.setup();
    const props = renderSheet();

    await user.click(screen.getByRole("button", { name: "保存资料" }));

    expect(screen.getByRole("alert")).toHaveTextContent("本机存储空间不足");
    expect(props.onSaved).not.toHaveBeenCalled();
    expect(props.onClose).not.toHaveBeenCalled();
  });

  it("tells the user the data stays on this device", () => {
    renderSheet();
    expect(screen.getByText(/不会上传服务器/)).toBeInTheDocument();
  });
});
