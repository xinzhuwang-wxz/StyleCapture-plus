import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { vi } from "vitest";

import { TryOnPhotoSheet } from "../src/features/profile/TryOnPhotoSheet";
import type {
  PhotoAlbum,
  ReferencePhoto
} from "../src/features/profile/photoStorage";

vi.mock("../src/media/downscaleImage", () => ({
  downscaleToDataUrl: vi.fn(async () => "data:image/jpeg;base64,bmV3LXBob3Rv")
}));

function photo(id: string, body = id): ReferencePhoto {
  return {
    id,
    dataUrl: `data:image/jpeg;base64,${window.btoa(body)}`,
    addedAt: "2026-08-09T00:00:00.000Z"
  };
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("try-on photo picker", () => {
  it("uses an existing photo from the same album as My profile", () => {
    const onChoose = vi.fn();
    const album: PhotoAlbum = {
      photos: [photo("a", "first"), photo("b", "second")],
      activeId: "a"
    };

    render(
      <TryOnPhotoSheet
        album={album}
        onAlbumChange={vi.fn()}
        onChoose={onChoose}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByRole("radio", { name: "第 1 张形象照，默认试穿照" })).toHaveAttribute(
      "aria-checked",
      "true"
    );
    fireEvent.click(screen.getByRole("radio", { name: "第 2 张形象照" }));
    fireEvent.click(screen.getByRole("button", { name: "使用这张形象试穿" }));

    expect(onChoose).toHaveBeenCalledTimes(1);
    const chosen = onChoose.mock.calls[0][0] as File;
    expect(chosen).toBeInstanceOf(File);
    expect(chosen.type).toBe("image/jpeg");
    expect(chosen.name).toContain("b");
  });

  it("can switch the default try-on portrait", () => {
    const onAlbumChange = vi.fn();
    const album: PhotoAlbum = {
      photos: [photo("a"), photo("b")],
      activeId: "a"
    };

    render(
      <TryOnPhotoSheet
        album={album}
        onAlbumChange={onAlbumChange}
        onChoose={vi.fn()}
        onClose={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("radio", { name: "第 2 张形象照" }));
    fireEvent.click(screen.getByRole("button", { name: "设为默认试穿照" }));
    expect(onAlbumChange).toHaveBeenCalledWith({ ...album, activeId: "b" });
  });

  it("saves a newly uploaded portrait to the shared album before try-on", async () => {
    const onChoose = vi.fn();
    const original = new File(["portrait"], "portrait.jpg", { type: "image/jpeg" });

    function Harness() {
      const [album, setAlbum] = useState<PhotoAlbum>({ photos: [], activeId: null });
      return (
        <TryOnPhotoSheet
          album={album}
          onAlbumChange={setAlbum}
          onChoose={onChoose}
          onClose={vi.fn()}
        />
      );
    }

    render(<Harness />);
    fireEvent.change(screen.getByLabelText("从相册新建试穿形象"), {
      target: { files: [original] }
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "使用这张形象试穿" })).toBeEnabled();
    });
    expect(screen.getByText("默认试穿照")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "使用这张形象试穿" }));
    expect(onChoose).toHaveBeenCalledWith(original);
  });

  it("closes only the picker when its close control is used", () => {
    const onClose = vi.fn();
    render(
      <TryOnPhotoSheet
        album={{ photos: [], activeId: null }}
        onAlbumChange={vi.fn()}
        onChoose={vi.fn()}
        onClose={onClose}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "关闭形象照选择" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
