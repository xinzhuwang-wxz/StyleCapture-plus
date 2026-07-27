import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { PhotoManagerSheet } from "../src/features/profile/PhotoManagerSheet";
import {
  MAX_REFERENCE_PHOTOS,
  emptyAlbum,
  type PhotoAlbum,
  type ReferencePhoto
} from "../src/features/profile/photoStorage";

vi.mock("../src/media/downscaleImage", () => ({
  REFERENCE_MAX_EDGE: 720,
  fitWithin: (w: number, h: number) => ({ width: w, height: h }),
  downscaleToDataUrl: vi.fn(async () => "data:image/jpeg;base64,shrunk")
}));

function photo(id: string): ReferencePhoto {
  return {
    id,
    dataUrl: `data:image/jpeg;base64,${id}`,
    addedAt: "2026-07-27T00:00:00.000Z"
  };
}

function useStorage(overrides: Partial<Storage> = {}) {
  const map = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: (key: string) => map.get(key) ?? null,
      setItem: (key: string, value: string) => void map.set(key, value),
      removeItem: (key: string) => void map.delete(key),
      clear: () => map.clear(),
      key: () => null,
      get length() {
        return map.size;
      },
      ...overrides
    } as Storage
  });
}

beforeEach(() => {
  useStorage();
  vi.stubGlobal("crypto", { ...globalThis.crypto, randomUUID: () => "new-id" });
});

function renderSheet(album: PhotoAlbum) {
  const props = {
    album,
    onChange: vi.fn(),
    onClose: vi.fn(),
    onNotice: vi.fn()
  };
  render(<PhotoManagerSheet {...props} />);
  return props;
}

function jpeg() {
  return new File(["x"], "me.jpg", { type: "image/jpeg" });
}

describe("photo manager", () => {
  it("shows guidance rather than an empty grid when there are no photos", () => {
    renderSheet(emptyAlbum());
    expect(screen.getByText("还没有形象照")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "设为试穿照" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "删除所选" })).toBeDisabled();
  });

  it("adds a downscaled photo and reports where it went", async () => {
    const props = renderSheet(emptyAlbum());
    fireEvent.change(screen.getByLabelText("上传形象照"), {
      target: { files: [jpeg()] }
    });
    await waitFor(() => expect(props.onChange).toHaveBeenCalled());
    expect(props.onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        activeId: "new-id",
        photos: [
          expect.objectContaining({ dataUrl: "data:image/jpeg;base64,shrunk" })
        ]
      })
    );
    expect(props.onNotice).toHaveBeenCalledWith("照片已保存在本机");
  });

  it("refuses a non-image without touching the album", async () => {
    const props = renderSheet(emptyAlbum());
    fireEvent.change(screen.getByLabelText("上传形象照"), {
      target: { files: [new File(["x"], "a.pdf", { type: "application/pdf" })] }
    });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/请选择/)
    );
    expect(props.onChange).not.toHaveBeenCalled();
  });

  it("blocks the upload button at the documented maximum", () => {
    const photos = Array.from({ length: MAX_REFERENCE_PHOTOS }, (_, i) =>
      photo(`p${i}`)
    );
    renderSheet({ photos, activeId: "p0" });
    expect(screen.getByRole("button", { name: "＋ 上传" })).toBeDisabled();
  });

  it("only offers set-as-reference when exactly one photo is picked", async () => {
    const user = userEvent.setup();
    const props = renderSheet({
      photos: [photo("a"), photo("b")],
      activeId: "a"
    });
    const setButton = screen.getByRole("button", { name: "设为试穿照" });
    expect(setButton).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /第 2 张形象照/ }));
    expect(setButton).toBeEnabled();
    await user.click(setButton);
    expect(props.onChange).toHaveBeenCalledWith(
      expect.objectContaining({ activeId: "b" })
    );

    // Two selected is ambiguous — there is no single reference to set.
    await user.click(screen.getByRole("button", { name: /第 1 张形象照/ }));
    await user.click(screen.getByRole("button", { name: /第 2 张形象照/ }));
    expect(screen.getByRole("button", { name: "设为试穿照" })).toBeDisabled();
  });

  it("deletes every selected photo at once", async () => {
    const user = userEvent.setup();
    const props = renderSheet({
      photos: [photo("a"), photo("b"), photo("c")],
      activeId: "a"
    });
    await user.click(screen.getByRole("button", { name: /第 1 张形象照/ }));
    await user.click(screen.getByRole("button", { name: /第 3 张形象照/ }));
    await user.click(screen.getByRole("button", { name: "删除所选" }));
    expect(props.onChange).toHaveBeenCalledWith(
      expect.objectContaining({ activeId: "b" })
    );
    expect(props.onNotice).toHaveBeenCalledWith("已删除 2 张");
  });

  it("marks which photo the try-on actually uses", () => {
    renderSheet({ photos: [photo("a"), photo("b")], activeId: "b" });
    expect(screen.getByText("✓ 试穿使用")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "第 2 张形象照（试穿使用中）" })
    ).toBeInTheDocument();
  });

  it("says the device is full instead of pretending the photo was saved", async () => {
    const quota = new Error("full");
    quota.name = "QuotaExceededError";
    useStorage({
      setItem: () => {
        throw quota;
      }
    });
    const props = renderSheet(emptyAlbum());
    fireEvent.change(screen.getByLabelText("上传形象照"), {
      target: { files: [jpeg()] }
    });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("本机存储放不下了")
    );
    expect(props.onChange).not.toHaveBeenCalled();
  });

  it("tells the user the photos never leave the device", () => {
    renderSheet(emptyAlbum());
    expect(screen.getByText(/不会上传服务器/)).toBeInTheDocument();
  });
});
