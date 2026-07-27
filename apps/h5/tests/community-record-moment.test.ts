import { vi } from "vitest";

import { recordClip } from "../src/features/community/world/recordMoment";

describe("recordClip", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    Reflect.deleteProperty(globalThis, "MediaRecorder");
  });

  it("stops the recorder and canvas tracks when painting a later frame fails", async () => {
    vi.useFakeTimers();
    const trackStop = vi.fn();
    const recorderStop = vi.fn();

    class MediaRecorderStub {
      static isTypeSupported() {
        return true;
      }

      state: RecordingState = "inactive";
      ondataavailable: ((event: BlobEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onstop: ((event: Event) => void) | null = null;

      start() {
        this.state = "recording";
      }

      stop() {
        recorderStop();
        this.state = "inactive";
        this.onstop?.(new Event("stop"));
      }
    }

    Object.defineProperty(globalThis, "MediaRecorder", {
      configurable: true,
      value: MediaRecorderStub
    });
    Object.defineProperty(HTMLCanvasElement.prototype, "captureStream", {
      configurable: true,
      value: vi.fn(() => ({
        getTracks: () => [{ stop: trackStop }]
      }))
    });

    const clip = recordClip({
      durationMs: 1000,
      framesPerSecond: 10,
      width: 320,
      height: 240,
      paint: (_context, frame) => {
        if (frame === 1) throw new Error("renderCard failed");
      }
    });
    const rejection = expect(clip).rejects.toThrow("renderCard failed");

    await vi.advanceTimersByTimeAsync(100);

    await rejection;
    expect(recorderStop).toHaveBeenCalledTimes(1);
    expect(trackStop).toHaveBeenCalledTimes(1);
  });
});
