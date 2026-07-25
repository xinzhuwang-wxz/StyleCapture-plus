import "@testing-library/jest-dom/vitest";

Object.defineProperty(URL, "createObjectURL", {
  configurable: true,
  value: vi.fn(() => "blob:preview")
});
Object.defineProperty(URL, "revokeObjectURL", {
  configurable: true,
  value: vi.fn()
});

const canvasContext = {
  fillStyle: "",
  font: "",
  fillRect: vi.fn(),
  fillText: vi.fn(),
  drawImage: vi.fn()
} as unknown as CanvasRenderingContext2D;

Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
  configurable: true,
  value: vi.fn(() => canvasContext)
});
