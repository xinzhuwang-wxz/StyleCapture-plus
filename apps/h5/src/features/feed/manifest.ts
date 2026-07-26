const FEED_MANIFEST_URL = "/feed/manifest.json";

export interface FeedAsset {
  assetId: string;
  sourcePageUrl: string;
  sourcePlatform: string;
  creatorName: string;
  licenseName: string;
  licenseUrl: string;
  localPath: string;
  categoryBucket: string;
  orientation: string;
}

type ManifestAsset = {
  asset_id?: unknown;
  source_page_url?: unknown;
  source_platform?: unknown;
  creator_name?: unknown;
  license_name?: unknown;
  license_url?: unknown;
  local_path?: unknown;
  content_type?: unknown;
  category_bucket?: unknown;
  orientation?: unknown;
  annotation_provenance?: unknown;
};

type FeedManifest = {
  schema_version?: unknown;
  assets?: unknown;
};

function requiredString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`Feed manifest 缺少 ${field}`);
  }
  return value.trim();
}

export function feedMediaUrl(localPath: string): string {
  const normalized = localPath.replaceAll("\\", "/");
  const segments = normalized.split("/");
  if (
    normalized.startsWith("/") ||
    segments.some((segment) => segment === "" || segment === ".." || segment === ".")
  ) {
    throw new Error("Feed 素材路径无效");
  }
  return `/feed/${segments.map(encodeURIComponent).join("/")}`;
}

export function feedPosterUrl(assetId: string): string {
  return feedMediaUrl(`posters/${assetId}.jpg`);
}

function parseAsset(value: unknown): FeedAsset | null {
  if (!value || typeof value !== "object") {
    throw new Error("Feed manifest 包含无效素材");
  }
  const asset = value as ManifestAsset;
  if (asset.content_type !== "video") {
    return null;
  }
  if (asset.annotation_provenance !== "curated_seed") {
    throw new Error("Feed 素材缺少 curated_seed 来源标记");
  }

  const localPath = requiredString(asset.local_path, "local_path");
  feedMediaUrl(localPath);
  return {
    assetId: requiredString(asset.asset_id, "asset_id"),
    sourcePageUrl: requiredString(asset.source_page_url, "source_page_url"),
    sourcePlatform: requiredString(asset.source_platform, "source_platform"),
    creatorName: requiredString(asset.creator_name, "creator_name"),
    licenseName: requiredString(asset.license_name, "license_name"),
    licenseUrl: requiredString(asset.license_url, "license_url"),
    localPath,
    categoryBucket: requiredString(asset.category_bucket, "category_bucket"),
    orientation: requiredString(asset.orientation, "orientation")
  };
}

export async function loadFeedManifest(
  signal?: AbortSignal
): Promise<FeedAsset[]> {
  const response = await fetch(FEED_MANIFEST_URL, {
    credentials: "same-origin",
    cache: "default",
    signal
  });
  if (!response.ok) {
    throw new Error("穿搭 Feed 暂时无法加载");
  }

  const manifest = (await response.json()) as FeedManifest;
  if (manifest.schema_version !== 1 || !Array.isArray(manifest.assets)) {
    throw new Error("Feed manifest 版本无效");
  }
  return manifest.assets
    .map(parseAsset)
    .filter((asset): asset is FeedAsset => asset !== null);
}
