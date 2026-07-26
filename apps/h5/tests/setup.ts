import "@testing-library/jest-dom/vitest";

Object.defineProperty(URL, "createObjectURL", {
  configurable: true,
  value: vi.fn(() => "blob:preview")
});
Object.defineProperty(URL, "revokeObjectURL", {
  configurable: true,
  value: vi.fn()
});

/**
 * jsdom has no canvas implementation, but the pixel world draws every frame.
 * A permissive stub lets components mount and run their render loop; assertions
 * about what is actually painted belong in the browser journey, not here.
 */
function createCanvasContextStub(): CanvasRenderingContext2D {
  const measured = { width: 24 } as TextMetrics;
  const gradient = { addColorStop: vi.fn() } as unknown as CanvasGradient;

  const store: Record<string, unknown> = {
    measureText: vi.fn(() => measured),
    createRadialGradient: vi.fn(() => gradient),
    createLinearGradient: vi.fn(() => gradient),
    getImageData: vi.fn(
      (_x: number, _y: number, width: number, height: number) => ({
        data: new Uint8ClampedArray(Math.max(4, width * height * 4)),
        width,
        height,
        colorSpace: "srgb" as const
      })
    )
  };

  return new Proxy(store, {
    get(target, property: string) {
      if (property in target) return target[property];
      // Unknown members are drawing calls or style properties; both are no-ops.
      const noop = vi.fn();
      target[property] = noop;
      return noop;
    },
    set(target, property: string, value) {
      target[property] = value;
      return true;
    }
  }) as unknown as CanvasRenderingContext2D;
}

Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
  configurable: true,
  value: vi.fn(() => createCanvasContextStub())
});

Object.defineProperty(HTMLCanvasElement.prototype, "toBlob", {
  configurable: true,
  value: vi.fn((callback: BlobCallback) =>
    callback(new Blob(["fake"], { type: "image/png" }))
  )
});

Object.defineProperty(HTMLCanvasElement.prototype, "toDataURL", {
  configurable: true,
  value: vi.fn(() => "data:image/png;base64,fake")
});

/** jsdom has no ResizeObserver; the canvas measures itself through one. */
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(globalThis, "ResizeObserver", {
  configurable: true,
  writable: true,
  value: ResizeObserverStub
});
