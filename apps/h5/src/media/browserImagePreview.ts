const HEIF_TYPES = new Set(["image/heic", "image/heif"]);

function fileType(file: File): string {
  if (file.type) return file.type.toLowerCase();
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension === "heic") return "image/heic";
  if (extension === "heif") return "image/heif";
  return "";
}

export function createBrowserImagePreview(file: File): string | null {
  return HEIF_TYPES.has(fileType(file)) ? null : URL.createObjectURL(file);
}

export function releaseBrowserImagePreview(previewUrl: string | null): void {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
}
