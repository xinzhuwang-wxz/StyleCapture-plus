import { renderHook, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { wardrobeApi } from "../src/api/client";
import { useDisplayImage } from "../src/features/wardrobe/useDisplayImage";

vi.mock("../src/api/client", () => ({
  wardrobeApi: {
    displayImage: vi.fn()
  }
}));

const displayImage = vi.mocked(wardrobeApi.displayImage);

describe("useDisplayImage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("reloads when background processing replaces the display asset", async () => {
    displayImage
      .mockResolvedValueOnce("blob:original")
      .mockResolvedValueOnce("blob:normalized");

    const { result, rerender } = renderHook(
      ({ refreshKey }) => useDisplayImage("item-1", refreshKey),
      { initialProps: { refreshKey: "processing:2026-07-25T00:00:00Z" } }
    );
    await waitFor(() => expect(result.current).toBe("blob:original"));

    rerender({ refreshKey: "ready:2026-07-25T00:00:30Z" });

    await waitFor(() => expect(result.current).toBe("blob:normalized"));
    expect(displayImage).toHaveBeenCalledTimes(2);
  });
});
