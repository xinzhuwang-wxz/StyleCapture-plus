/**
 * gifenc ships as untyped ESM. This declares only the surface the share export
 * uses, so a wrong call still fails the type check.
 */
declare module "gifenc" {
  export type GifPalette = number[][];

  export type WriteFrameOptions = {
    palette?: GifPalette;
    /** Frame duration in milliseconds. */
    delay?: number;
    transparent?: boolean;
    transparentIndex?: number;
    repeat?: number;
    /** GIF disposal method; 1 leaves the previous frame in place. */
    dispose?: number;
    first?: boolean;
    colorDepth?: number;
  };

  export type GifEncoderInstance = {
    writeFrame(
      index: Uint8Array,
      width: number,
      height: number,
      options?: WriteFrameOptions
    ): void;
    finish(): void;
    bytesView(): Uint8Array<ArrayBuffer>;
    bytes(): number[];
    reset(): void;
  };

  export function GIFEncoder(options?: {
    auto?: boolean;
    initialCapacity?: number;
  }): GifEncoderInstance;

  export function quantize(
    data: Uint8Array | Uint8ClampedArray,
    maxColors: number,
    options?: { format?: "rgb565" | "rgb444" | "rgba4444"; oneBitAlpha?: boolean }
  ): GifPalette;

  export function applyPalette(
    data: Uint8Array | Uint8ClampedArray,
    palette: GifPalette,
    format?: "rgb565" | "rgb444" | "rgba4444"
  ): Uint8Array;

  export function snapColorsToPalette(
    palette: GifPalette,
    knownColors: GifPalette,
    threshold?: number
  ): void;
}
