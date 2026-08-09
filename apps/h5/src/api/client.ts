import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type CaptureAccepted = components["schemas"]["CaptureAcceptedResponse"];
export type FeedFrameContext = components["schemas"]["FeedFrameContextBody"];
export type Item = components["schemas"]["ItemResponse"];
export type ItemPresentation = components["schemas"]["ItemPresentationResponse"];
export type Job = components["schemas"]["JobResponse"];
export type Look = components["schemas"]["LookSummaryResponse"];
export type LookDetail = components["schemas"]["LookDetailResponse"];
export type LookDeletion = components["schemas"]["LookDeletionResponse"];
export type OutfitPlan = components["schemas"]["OutfitPlanResponse"];
export type OutfitPlanSet = components["schemas"]["OutfitPlanSetResponse"];
export type PixelTrial = components["schemas"]["PixelTrialResponse"];
export type PurchaseDemand = components["schemas"]["PurchaseDemandResponse"];
export type SavedOutfitLook = components["schemas"]["SavedOutfitLookResponse"];
export type Ownership = components["schemas"]["OwnershipState"];
export type RenderArtifact = components["schemas"]["RenderArtifactResponse"];
export type RenderKind = components["schemas"]["RenderArtifactKind"];
export type SourceKind = components["schemas"]["CaptureSourceKind"];

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
const NORMALIZED_UPLOAD_MAX_EDGE = 1600;
const NORMALIZED_UPLOAD_QUALITY = 0.86;
const SUPPORTED_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
  "image/heif"
]);

const client = createClient<paths>({
  baseUrl:
    typeof window === "undefined" ? "http://localhost" : window.location.origin,
  fetch: (request) => fetch(request)
});
let sessionPromise: Promise<void> | null = null;

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
  };
};

const PRODUCT_ERROR_MESSAGES: Record<string, string> = {
  render_idempotency_conflict: "穿搭内容已经更新，请稍后重新生成成片",
  render_dispatch_unavailable: "成片任务已保存，后台服务恢复后会继续",
  render_artifact_not_found: "这张穿搭成片暂时不可用",
  pixel_trial_idempotency_conflict: "这张全身照已经重新提交，请刷新后再试",
  pixel_trial_dispatch_unavailable: "像素形象任务已保存，后台服务恢复后会继续",
  pixel_trial_not_found: "这次像素形象生成暂时不可用",
  image_format_mismatch: "手机相册返回了不一致的图片格式，请重新选择；我们会自动识别 HEIC",
  image_decode_failed: "这张照片暂时无法读取，请换一张原图再试",
  image_dimensions_invalid: "照片分辨率过高，请选择普通清晰度的全身照",
  upload_content_type_mismatch: "照片格式在上传中发生变化，请重新选择照片",
  upload_hash_mismatch: "照片上传中断，请重新选择照片",
  upload_size_mismatch: "照片上传不完整，请重新选择照片",
  upload_unattached_quota_exceeded: "待处理照片较多，请删除旧草稿后再试",
  item_presentation_dispatch_unavailable: "像素展示图任务已保存，后台服务恢复后会继续",
  item_presentation_not_found: "这张像素展示图暂时不可用",
  job_not_retryable: "当前任务正在处理或已经完成，无需重试",
  source_deleted_not_retryable: "原始图片已删除，无法再次识别",
  item_update_invalid: "修改内容不符合衣橱要求",
  outfit_wardrobe_empty: "衣橱里还没有可搭配的真实单品",
  outfit_plan_invalid: "这套穿搭中的单品已变化，请重新生成",
  // 没有这两条时，限流会被调用方的兜底文案盖掉，用户看到的是「失败了」而不是
  // 「稍等再试」——后者才是能照着做的。
  ai_quota_exceeded: "AI 请求有点密集，稍等几秒再试就好",
  ai_capacity_unavailable: "AI 服务正忙，请稍后重试"
};

export class ProductApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ProductApiError";
    this.code = code;
  }
}

async function ensureSession(): Promise<void> {
  if (!sessionPromise) {
    sessionPromise = fetch("/v1/session", {
      method: "POST",
      credentials: "same-origin"
    }).then((response) => {
      if (!response.ok) {
        throw new ProductApiError("session_unavailable", "暂时无法建立私人衣橱会话");
      }
    });
    sessionPromise.catch(() => {
      sessionPromise = null;
    });
  }
  return sessionPromise;
}

export function validateImage(file: File): string | null {
  const contentType = contentTypeFor(file);
  if (!SUPPORTED_TYPES.has(contentType)) {
    return "请选择 JPG、PNG、WebP 或 HEIC 图片";
  }
  if (file.size <= 0 || file.size > MAX_UPLOAD_BYTES) {
    return "图片需小于 20MB";
  }
  return null;
}

function contentTypeFor(file: File): string {
  if (file.type) {
    return file.type.toLowerCase();
  }
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (extension === "heic") return "image/heic";
  if (extension === "heif") return "image/heif";
  if (extension === "jpg" || extension === "jpeg") return "image/jpeg";
  if (extension === "png") return "image/png";
  if (extension === "webp") return "image/webp";
  return "";
}

type UploadImage = {
  file: File;
  contentType: string;
};

function withContentType(file: File, contentType: string): File {
  if (file.type.toLowerCase() === contentType) {
    return file;
  }
  return new File([file], file.name, {
    type: contentType,
    lastModified: file.lastModified
  });
}

export async function detectedContentTypeFor(file: File): Promise<string> {
  const source = file.slice(0, 16);
  const buffer =
    typeof source.arrayBuffer === "function"
      ? await source.arrayBuffer()
      : await new Promise<ArrayBuffer>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result as ArrayBuffer);
          reader.onerror = () => reject(reader.error ?? new Error("image signature read failed"));
          reader.readAsArrayBuffer(source);
        });
  const signature = new Uint8Array(buffer);
  if (signature.length >= 3 && signature[0] === 0xff && signature[1] === 0xd8 && signature[2] === 0xff) {
    return "image/jpeg";
  }
  if (
    signature.length >= 8 &&
    signature[0] === 0x89 &&
    signature[1] === 0x50 &&
    signature[2] === 0x4e &&
    signature[3] === 0x47 &&
    signature[4] === 0x0d &&
    signature[5] === 0x0a &&
    signature[6] === 0x1a &&
    signature[7] === 0x0a
  ) {
    return "image/png";
  }
  if (
    signature.length >= 12 &&
    String.fromCharCode(...signature.slice(0, 4)) === "RIFF" &&
    String.fromCharCode(...signature.slice(8, 12)) === "WEBP"
  ) {
    return "image/webp";
  }
  if (
    signature.length >= 12 &&
    String.fromCharCode(...signature.slice(4, 8)) === "ftyp"
  ) {
    const brand = String.fromCharCode(...signature.slice(8, 12));
    if (["heic", "heix", "hevc", "hevx", "heim", "heis", "mif1", "msf1"].includes(brand)) {
      return brand === "mif1" || brand === "msf1" ? "image/heif" : "image/heic";
    }
  }
  return contentTypeFor(file);
}

function normalizedFileName(fileName: string): string {
  const base = fileName.replace(/\.[^.]+$/, "");
  return `${base || "stylecapture-upload"}.jpg`;
}

async function canvasToBlob(
  canvas: HTMLCanvasElement,
  type: string,
  quality: number
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob);
        } else {
          reject(new Error("image normalization produced an empty blob"));
        }
      },
      type,
      quality
    );
  });
}

async function decodeImageFile(file: File): Promise<ImageBitmap | HTMLImageElement> {
  if (typeof createImageBitmap === "function") {
    return createImageBitmap(file);
  }
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    const timeout = window.setTimeout(() => {
      URL.revokeObjectURL(url);
      reject(new Error("image decode timed out"));
    }, 4_000);
    image.onload = () => {
      window.clearTimeout(timeout);
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      window.clearTimeout(timeout);
      URL.revokeObjectURL(url);
      reject(new Error("image decode failed"));
    };
    image.src = url;
  });
}

async function normalizeImageForUpload(file: File): Promise<UploadImage> {
  // iOS photo pickers can report a JPEG MIME type for HEIC bytes. Sniff the
  // immutable source before preparing the signed upload so the server sees a
  // content type that matches the actual payload.
  const contentType = await detectedContentTypeFor(file);
  if (!SUPPORTED_TYPES.has(contentType)) {
    return { file, contentType };
  }
  const sourceFile = withContentType(file, contentType);
  if (
    typeof window === "undefined" ||
    typeof document === "undefined" ||
    typeof HTMLCanvasElement === "undefined" ||
    (typeof navigator !== "undefined" && navigator.userAgent.toLowerCase().includes("jsdom"))
  ) {
    return { file: sourceFile, contentType };
  }

  try {
    const decoded = await decodeImageFile(sourceFile);
    const width = decoded.width;
    const height = decoded.height;
    if (width <= 0 || height <= 0) {
      return { file: sourceFile, contentType };
    }

    const scale = Math.min(1, NORMALIZED_UPLOAD_MAX_EDGE / Math.max(width, height));
    const outputWidth = Math.max(1, Math.round(width * scale));
    const outputHeight = Math.max(1, Math.round(height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = outputWidth;
    canvas.height = outputHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      return { file: sourceFile, contentType };
    }
    context.drawImage(decoded, 0, 0, outputWidth, outputHeight);
    if ("close" in decoded && typeof decoded.close === "function") {
      decoded.close();
    }

    const blob = await canvasToBlob(
      canvas,
      "image/jpeg",
      NORMALIZED_UPLOAD_QUALITY
    );
    if (blob.size <= 0 || blob.size > MAX_UPLOAD_BYTES) {
      return { file: sourceFile, contentType };
    }
    return {
      file: new File([blob], normalizedFileName(file.name), {
        type: "image/jpeg",
        lastModified: file.lastModified
      }),
      contentType: "image/jpeg"
    };
  } catch {
    return { file: sourceFile, contentType };
  }
}

async function sha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function throwApiError(error: unknown, fallback: string): never {
  const payload = error as ApiErrorPayload | undefined;
  const code = payload?.error?.code ?? "request_failed";
  throw new ProductApiError(
    code,
    PRODUCT_ERROR_MESSAGES[code] ?? fallback
  );
}

async function uploadPrivateImageWithDigest(
  file: File
): Promise<{ objectKey: string; digest: string }> {
  const { file: uploadFile, contentType } = await normalizeImageForUpload(file);
  const validationError = validateImage(uploadFile);
  if (validationError) {
    throw new ProductApiError("image_invalid", validationError);
  }
  await ensureSession();
  const digest = await sha256(uploadFile);
  const prepared = await client.POST("/v1/uploads/prepare", {
    body: {
      file_name: uploadFile.name,
      content_type: contentType,
      byte_size: uploadFile.size,
      sha256: digest
    }
  });
  if (!prepared.data) {
    throwApiError(prepared.error, "暂时无法准备上传");
  }
  const uploadResponse = await fetch(prepared.data.upload_url, {
    method: "PUT",
    headers: {
      "Content-Type": contentType,
      "X-Upload-Token": prepared.data.upload_token
    },
    body: uploadFile
  });
  if (!uploadResponse.ok) {
    throwApiError(await uploadResponse.json().catch(() => undefined), "图片上传失败");
  }
  return { objectKey: prepared.data.object_key, digest };
}

async function uploadPrivateImage(file: File): Promise<string> {
  return (await uploadPrivateImageWithDigest(file)).objectKey;
}

async function discardPrivateUpload(objectKey: string): Promise<void> {
  await ensureSession();
  const encodedKey = objectKey
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  const response = await fetch(`/v1/uploads/${encodedKey}`, {
    method: "DELETE",
    credentials: "include"
  });
  if (!response.ok && response.status !== 404) {
    throw new Error("临时全身照清理失败");
  }
}

async function createPixelTrial(
  file: File,
  idempotencyKey: string
): Promise<PixelTrial> {
  const subjectObjectKey = await uploadPrivateImage(file);
  const response = await client.POST("/v1/pixel-trials", {
    params: {
      header: { "Idempotency-Key": idempotencyKey }
    },
    body: { subject_object_key: subjectObjectKey }
  });
  if (!response.data) {
    await discardPrivateUpload(subjectObjectKey).catch(() => undefined);
    throwApiError(response.error, "像素形象任务没有启动");
  }
  return response.data;
}

async function getPixelTrial(trialId: string): Promise<PixelTrial> {
  await ensureSession();
  const response = await client.GET("/v1/pixel-trials/{trial_id}", {
    params: { path: { trial_id: trialId } }
  });
  if (!response.data) {
    throwApiError(response.error, "像素形象状态暂时无法更新");
  }
  return response.data;
}

async function deletePixelTrial(trialId: string): Promise<void> {
  await ensureSession();
  const response = await client.DELETE("/v1/pixel-trials/{trial_id}", {
    params: { path: { trial_id: trialId } }
  });
  if (response.error) {
    throwApiError(response.error, "像素形象暂时无法删除");
  }
}

async function ensureItemPixelPresentation(itemId: string): Promise<ItemPresentation> {
  await ensureSession();
  const response = await client.POST("/v1/items/{item_id}/presentations/pixel", {
    params: {
      path: { item_id: itemId },
      header: { "Idempotency-Key": `item-pixel:${itemId}` }
    }
  });
  if (!response.data) {
    throwApiError(response.error, "像素展示图任务没有启动");
  }
  return response.data;
}

async function ensureItemFlatLayPresentation(itemId: string): Promise<ItemPresentation> {
  await ensureSession();
  const response = await client.POST("/v1/items/{item_id}/presentations/flat-lay", {
    params: {
      path: { item_id: itemId },
      header: { "Idempotency-Key": `item-flat-lay:${itemId}` }
    }
  });
  if (!response.data) {
    throwApiError(response.error, "真实单品白底图暂时无法生成");
  }
  return response.data;
}

async function getItemPresentation(assetId: string): Promise<ItemPresentation> {
  await ensureSession();
  const response = await client.GET("/v1/item-presentations/{asset_id}", {
    params: { path: { asset_id: assetId } }
  });
  if (!response.data) {
    throwApiError(response.error, "像素展示图状态暂时无法更新");
  }
  return response.data;
}

async function submitCapture(
  file: File,
  sourceKind: SourceKind,
  ownership: Ownership,
  idempotencyKey: string,
  intent: "item" | "whole_outfit" = "item",
  feedContext?: FeedFrameContext
): Promise<CaptureAccepted> {
  const { objectKey, digest } = await uploadPrivateImageWithDigest(file);
  const submitted = await client.POST("/v1/captures", {
    params: {
      header: {
        "Idempotency-Key": idempotencyKey
      }
    },
    body: {
      object_key: objectKey,
      sha256: digest,
      source_kind: sourceKind,
      ownership,
      intent,
      feed_context: feedContext
    }
  });
  if (!submitted.data) {
    throwApiError(submitted.error, "衣服已安全上传，但入库任务未能启动");
  }
  return submitted.data;
}

async function ingest(
  file: File,
  sourceKind: SourceKind,
  ownership: Ownership,
  idempotencyKey: string,
  intent: "item" | "whole_outfit" = "item"
): Promise<CaptureAccepted> {
  return submitCapture(file, sourceKind, ownership, idempotencyKey, intent);
}

async function ingestFeedFrame(
  file: File,
  feedContext: FeedFrameContext,
  idempotencyKey: string,
  intent: "item" | "whole_outfit" = "item"
): Promise<CaptureAccepted> {
  return submitCapture(
    file,
    "feed",
    "inspiration",
    idempotencyKey,
    intent,
    feedContext
  );
}

async function listItems(): Promise<Item[]> {
  await ensureSession();
  const response = await client.GET("/v1/items", {
    params: {}
  });
  if (!response.data) {
    throwApiError(response.error, "衣橱暂时无法加载");
  }
  return response.data.items;
}

async function listLooks(): Promise<Look[]> {
  await ensureSession();
  const response = await client.GET("/v1/looks", { params: {} });
  if (!response.data) {
    throwApiError(response.error, "穿搭衣橱暂时无法加载");
  }
  return response.data.looks;
}

async function getLook(lookId: string): Promise<LookDetail> {
  await ensureSession();
  const response = await client.GET("/v1/looks/{look_id}", {
    params: { path: { look_id: lookId } }
  });
  if (!response.data) {
    throwApiError(response.error, "这套穿搭暂时无法打开");
  }
  return response.data;
}

async function addLikingReason(
  lookId: string,
  reason: string,
  idempotencyKey: string
): Promise<void> {
  await ensureSession();
  const response = await client.POST("/v1/looks/{look_id}/feedback", {
    params: {
      path: { look_id: lookId },
      header: { "Idempotency-Key": idempotencyKey }
    },
    body: { reason }
  });
  if (!response.data) {
    throwApiError(response.error, "喜欢原因没有保存");
  }
}

async function retryLook(lookId: string): Promise<void> {
  await ensureSession();
  const response = await client.POST("/v1/looks/{look_id}/retry", {
    params: { path: { look_id: lookId } }
  });
  if (!response.data) {
    throwApiError(response.error, "这套穿搭暂时无法重试");
  }
}

async function listRenders(lookId: string): Promise<RenderArtifact[]> {
  await ensureSession();
  const response = await client.GET("/v1/looks/{look_id}/renders", {
    params: { path: { look_id: lookId } }
  });
  if (!response.data) {
    throwApiError(response.error, "穿搭成片暂时无法加载");
  }
  return response.data.renders;
}

async function createRender(
  lookId: string,
  kind: RenderKind,
  idempotencyKey: string,
  subjectObjectKey?: string
): Promise<RenderArtifact> {
  await ensureSession();
  const response = await client.POST("/v1/looks/{look_id}/renders", {
    params: {
      path: { look_id: lookId },
      header: { "Idempotency-Key": idempotencyKey }
    },
    body: { kind, subject_object_key: subjectObjectKey }
  });
  if (!response.data) {
    throwApiError(response.error, "成片任务没有启动");
  }
  return response.data;
}

async function deleteTryOnSubject(artifactId: string): Promise<void> {
  await ensureSession();
  const response = await client.DELETE(
    "/v1/render-artifacts/{artifact_id}/subject",
    {
      params: { path: { artifact_id: artifactId } }
    }
  );
  if (response.error) {
    throwApiError(response.error, "试穿原照暂时无法删除");
  }
}

async function getJob(jobId: string): Promise<Job> {
  await ensureSession();
  const response = await client.GET("/v1/jobs/{job_id}", {
    params: {
      path: { job_id: jobId }
    }
  });
  if (!response.data) {
    throwApiError(response.error, "处理状态暂时无法更新");
  }
  return response.data;
}

async function retryJob(jobId: string): Promise<Job> {
  await ensureSession();
  const response = await client.POST("/v1/jobs/{job_id}/retry", {
    params: {
      path: { job_id: jobId }
    }
  });
  if (!response.data) {
    throwApiError(response.error, "暂时无法重试");
  }
  return response.data;
}

async function retryItem(itemId: string): Promise<void> {
  await ensureSession();
  const response = await client.POST("/v1/items/{item_id}/retry", {
    params: {
      path: { item_id: itemId }
    }
  });
  if (!response.data) {
    throwApiError(response.error, "暂时无法重新识别");
  }
}

async function retryItemPixel(itemId: string): Promise<ItemPresentation> {
  await ensureSession();
  const response = await client.POST(
    "/v1/items/{item_id}/presentations/pixel/retry",
    {
      params: { path: { item_id: itemId } }
    }
  );
  if (!response.data) {
    throwApiError(response.error, "像素展示图暂时无法重试");
  }
  return response.data;
}

async function updateItem(
  itemId: string,
  changes: {
    ownership?: Ownership;
    corrections?: Record<string, string | string[]>;
  }
): Promise<Item> {
  await ensureSession();
  const response = await client.PATCH("/v1/items/{item_id}", {
    params: {
      path: { item_id: itemId }
    },
    body: {
      ownership: changes.ownership,
      corrections: changes.corrections ?? {}
    }
  });
  if (!response.data) {
    throwApiError(response.error, "修改没有保存");
  }
  return response.data;
}

async function deleteSource(itemId: string): Promise<void> {
  await ensureSession();
  const response = await client.DELETE("/v1/items/{item_id}/source", {
    params: {
      path: { item_id: itemId }
    }
  });
  if (response.error) {
    throwApiError(response.error, "原图删除失败");
  }
}

async function deleteItem(itemId: string): Promise<void> {
  await ensureSession();
  const response = await client.DELETE("/v1/items/{item_id}", {
    params: {
      path: { item_id: itemId }
    }
  });
  if (response.error) {
    throwApiError(response.error, "这件单品暂时无法删除");
  }
}

async function deleteLook(
  lookId: string,
  deleteItems: boolean
): Promise<LookDeletion> {
  await ensureSession();
  const response = await client.DELETE("/v1/looks/{look_id}", {
    params: {
      path: { look_id: lookId },
      query: { delete_items: deleteItems }
    }
  });
  if (!response.data) {
    throwApiError(response.error, "这套穿搭暂时无法删除");
  }
  return response.data;
}

async function displayImage(itemId: string): Promise<string> {
  await ensureSession();
  return `/v1/items/${encodeURIComponent(itemId)}/image`;
}

async function sourceImage(itemId: string): Promise<string> {
  await ensureSession();
  return `/v1/items/${encodeURIComponent(itemId)}/source`;
}

async function planOutfits(input: {
  scene: string;
  outfitCount?: 3 | 4;
  style?: string;
  weather?: string;
  formality?: string;
  comfort?: string;
  anchorItemId?: string;
  mustIncludeItemIds?: string[];
  excludeItemIds?: string[];
}): Promise<OutfitPlanSet> {
  await ensureSession();
  const response = await client.POST("/v1/outfit-plans", {
    body: {
      scene: input.scene,
      outfit_count: input.outfitCount ?? 4,
      style: input.style,
      weather: input.weather,
      formality: input.formality,
      comfort: input.comfort,
      anchor_item_id: input.anchorItemId,
      must_include_item_ids: input.mustIncludeItemIds ?? [],
      exclude_item_ids: input.excludeItemIds ?? []
    }
  });
  if (!response.data) {
    throwApiError(response.error, "暂时无法生成穿搭，请稍后再试");
  }
  return response.data;
}

async function planOutfitsProgressively(
  input: {
    scene: string;
    outfitCount?: 3 | 4;
    style?: string;
    weather?: string;
    formality?: string;
    comfort?: string;
    anchorItemId?: string;
    mustIncludeItemIds?: string[];
    excludeItemIds?: string[];
  },
  onProgress: (result: OutfitPlanSet, complete: boolean) => void
): Promise<OutfitPlanSet> {
  await ensureSession();
  const response = await fetch("/v1/outfit-plans/stream", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scene: input.scene,
      outfit_count: input.outfitCount ?? 4,
      style: input.style,
      weather: input.weather,
      formality: input.formality,
      comfort: input.comfort,
      anchor_item_id: input.anchorItemId,
      must_include_item_ids: input.mustIncludeItemIds ?? [],
      exclude_item_ids: input.excludeItemIds ?? []
    })
  });
  if (!response.ok || !response.body) {
    throwApiError(
      await response.json().catch(() => undefined),
      "暂时无法生成穿搭，请稍后再试"
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  let progressive: OutfitPlanSet | null = null;
  let completed: OutfitPlanSet | null = null;

  function consume(line: string) {
    if (!line.trim()) return;
    const event = JSON.parse(line) as
      | {
          type: "plan";
          request_id: string;
          trace_id: string;
          plan: OutfitPlan;
          explanation_state: OutfitPlanSet["explanation_state"];
        }
      | { type: "complete"; result: OutfitPlanSet };
    if (event.type === "complete") {
      completed = event.result;
      onProgress(event.result, true);
      return;
    }
    const next: OutfitPlanSet = {
      request_id: event.request_id,
      trace_id: event.trace_id,
      plans: [...(progressive?.plans ?? []), event.plan],
      degraded: false,
      degradation_reason: null,
      explanation_state: event.explanation_state
    };
    progressive = next;
    onProgress(next, false);
  }

  while (true) {
    const { done, value } = await reader.read();
    pending += decoder.decode(value, { stream: !done });
    const lines = pending.split("\n");
    pending = lines.pop() ?? "";
    lines.forEach(consume);
    if (done) break;
  }
  consume(pending);
  if (completed) return completed;
  if (progressive) return progressive;
  throw new ProductApiError("outfit_stream_empty", "AI 没有返回可用的穿搭方案");
}

async function saveOutfitPlan(
  plan: OutfitPlan,
  idempotencyKey: string
): Promise<SavedOutfitLook> {
  await ensureSession();
  const response = await client.POST("/v1/outfit-plans/{plan_id}/save-look", {
    params: {
      path: { plan_id: plan.id },
      header: { "Idempotency-Key": idempotencyKey }
    },
    body: {
      save_token: plan.save_token
    }
  });
  if (!response.data) {
    throwApiError(response.error, "这套穿搭暂时没有保存，请稍后再试");
  }
  return response.data;
}

async function replaceOutfitSlot(
  plan: OutfitPlan,
  role: OutfitPlan["slots"][number]["role"]
): Promise<OutfitPlan> {
  await ensureSession();
  const response = await client.POST(
    "/v1/outfit-plans/{plan_id}/replace-slot",
    {
      params: { path: { plan_id: plan.id } },
      body: {
        save_token: plan.save_token,
        role
      }
    }
  );
  if (!response.data) {
    throwApiError(response.error, "衣橱里暂时没有合适的替换单品");
  }
  return response.data;
}

async function listPurchaseDemands(lookId: string): Promise<PurchaseDemand[]> {
  await ensureSession();
  const response = await client.GET(
    "/v1/outfit-plans/saved-looks/{look_id}/purchase-list",
    {
      params: { path: { look_id: lookId } }
    }
  );
  if (!response.data) {
    throwApiError(response.error, "补齐清单暂时无法加载");
  }
  return response.data.demands;
}

async function advancePurchaseDemand(
  demandId: string,
  status: PurchaseDemand["status"]
): Promise<PurchaseDemand> {
  await ensureSession();
  const response = await client.PATCH(
    "/v1/outfit-plans/purchase-demands/{demand_id}",
    {
      params: { path: { demand_id: demandId } },
      body: { status }
    }
  );
  if (!response.data) {
    throwApiError(response.error, "购买状态没有更新");
  }
  return response.data;
}

export const wardrobeApi = {
  ingest,
  ingestFeedFrame,
  listItems,
  listLooks,
  getLook,
  addLikingReason,
  retryLook,
  listRenders,
  createRender,
  deleteTryOnSubject,
  createPixelTrial,
  getPixelTrial,
  deletePixelTrial,
  ensureItemPixelPresentation,
  ensureItemFlatLayPresentation,
  getItemPresentation,
  uploadPrivateImage,
  discardPrivateUpload,
  getJob,
  retryJob,
  retryItem,
  retryItemPixel,
  updateItem,
  deleteItem,
  deleteLook,
  deleteSource,
  displayImage,
  sourceImage,
  planOutfits,
  planOutfitsProgressively,
  replaceOutfitSlot,
  listPurchaseDemands,
  advancePurchaseDemand,
  saveOutfitPlan
};
