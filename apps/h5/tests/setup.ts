import "@testing-library/jest-dom/vitest";

Object.defineProperty(URL, "createObjectURL", {
  configurable: true,
  value: vi.fn(() => "blob:preview")
});
Object.defineProperty(URL, "revokeObjectURL", {
  configurable: true,
  value: vi.fn()
});
Object.defineProperty(HTMLMediaElement.prototype, "play", {
  configurable: true,
  value: vi.fn().mockResolvedValue(undefined)
});
Object.defineProperty(HTMLMediaElement.prototype, "pause", {
  configurable: true,
  value: vi.fn()
});
