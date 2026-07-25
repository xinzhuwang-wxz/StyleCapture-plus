import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type CaptureAccepted = components["schemas"]["CaptureAcceptedResponse"];
export type FeedFrameContext = components["schemas"]["FeedFrameContextBody"];
export type Item = components["schemas"]["ItemResponse"];
export type Job = components["schemas"]["JobResponse"];
export type Look = components["schemas"]["LookSummaryResponse"];
export type LookDetail = components["schemas"]["LookDetailResponse"];
export type Ownership = components["schemas"]["OwnershipState"];
export type RenderArtifact = components["schemas"]["RenderArtifactResponse"];
export type RenderKind = components["schemas"]["RenderArtifactKind"];
export type SourceKind = components["schemas"]["CaptureSourceKind"];

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
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
  job_not_retryable: "当前任务正在处理或已经完成，无需重试",
  source_deleted_not_retryable: "原始图片已删除，无法再次识别",
  item_update_invalid: "修改内容不符合衣橱要求"
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

async function submitCapture(
  file: File,
  sourceKind: SourceKind,
  ownership: Ownership,
  idempotencyKey: string,
  feedContext?: FeedFrameContext
): Promise<CaptureAccepted> {
  const validationError = validateImage(file);
  if (validationError) {
    throw new ProductApiError("image_invalid", validationError);
  }
  await ensureSession();
  const digest = await sha256(file);
  const contentType = contentTypeFor(file);
  const prepared = await client.POST("/v1/uploads/prepare", {
    body: {
      file_name: file.name,
      content_type: contentType,
      byte_size: file.size,
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
    body: file
  });
  if (!uploadResponse.ok) {
    throwApiError(await uploadResponse.json().catch(() => undefined), "图片上传失败");
  }
  const submitted = await client.POST("/v1/captures", {
    params: {
      header: {
        "Idempotency-Key": idempotencyKey
      }
    },
    body: {
      object_key: prepared.data.object_key,
      sha256: digest,
      source_kind: sourceKind,
      ownership,
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
  idempotencyKey: string
): Promise<CaptureAccepted> {
  return submitCapture(file, sourceKind, ownership, idempotencyKey);
}

async function ingestFeedFrame(
  file: File,
  feedContext: FeedFrameContext,
  idempotencyKey: string
): Promise<CaptureAccepted> {
  return submitCapture(
    file,
    "feed",
    "inspiration",
    idempotencyKey,
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
  idempotencyKey: string
): Promise<RenderArtifact> {
  await ensureSession();
  const response = await client.POST("/v1/looks/{look_id}/renders", {
    params: {
      path: { look_id: lookId },
      header: { "Idempotency-Key": idempotencyKey }
    },
    body: { kind }
  });
  if (!response.data) {
    throwApiError(response.error, "成片任务没有启动");
  }
  return response.data;
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

async function displayImage(itemId: string): Promise<string> {
  await ensureSession();
  const response = await fetch(`/v1/items/${itemId}/image`, {
    cache: "no-store"
  });
  if (!response.ok) {
    throwApiError(await response.json().catch(() => undefined), "衣橱展示图暂时不可用");
  }
  return URL.createObjectURL(await response.blob());
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
  getJob,
  retryJob,
  retryItem,
  updateItem,
  deleteSource,
  displayImage
};
