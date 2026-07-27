/**
 * 只存在这台设备上的小块数据。
 *
 * 身材数据和形象照都不该上传服务器，所以它们落在 localStorage。但浏览器存储
 * 是会失败的：隐私模式下写入直接抛错，容量满了也抛错，用户还可能手工改坏内容。
 * 这个模块把这些情况都变成明确的结果，而不是让页面白屏。
 *
 * 读：坏数据一律回落到默认值，永远不抛。
 * 写：容量不足是**可见的失败**，不能假装存上了——那会让用户以为资料保存成功。
 *
 * 键名沿用仓库已有约定 `stylecapture:<feature>:v<n>`
 * （见 `features/profile/ProfileScreen.tsx` 的 PIXEL_TRIAL_STORAGE_KEY）。
 */

export type LocalStoreDefinition<T> = {
  /** 完整键名，含版本号。改结构就换版本，旧数据自然被忽略。 */
  key: string;
  /** 读不到、读坏了、版本对不上时用它。每次调用返回新对象。 */
  fallback: () => T;
  /**
   * 校验并归一化任意 JSON。返回 null 表示这份数据不可用。
   * 写成校验而不是断言，是因为 localStorage 的内容用户可以随手改。
   */
  parse: (raw: unknown) => T | null;
};

export type WriteResult =
  | { ok: true }
  | { ok: false; reason: "unavailable" | "quota" | "failed" };

function storage(): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage;
  } catch {
    // 某些浏览器在禁用 cookie 时，连访问这个属性都会抛。
    return null;
  }
}

export function readLocal<T>(definition: LocalStoreDefinition<T>): T {
  const store = storage();
  if (!store) return definition.fallback();

  let raw: string | null = null;
  try {
    raw = store.getItem(definition.key);
  } catch {
    return definition.fallback();
  }
  if (raw === null) return definition.fallback();

  try {
    const parsed = definition.parse(JSON.parse(raw) as unknown);
    return parsed ?? definition.fallback();
  } catch {
    return definition.fallback();
  }
}

export function writeLocal<T>(
  definition: LocalStoreDefinition<T>,
  value: T
): WriteResult {
  const store = storage();
  if (!store) return { ok: false, reason: "unavailable" };

  try {
    store.setItem(definition.key, JSON.stringify(value));
    return { ok: true };
  } catch (error) {
    return { ok: false, reason: isQuotaError(error) ? "quota" : "failed" };
  }
}

export function clearLocal<T>(definition: LocalStoreDefinition<T>): void {
  const store = storage();
  if (!store) return;
  try {
    store.removeItem(definition.key);
  } catch {
    // 清不掉也没有可做的补救。
  }
}

/**
 * 容量超限在各浏览器里的表现不一致：名字、code 都不同，Safari 无痕模式甚至
 * 只给一个普通 Error。所以宁可多认几种。
 */
function isQuotaError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  if (error.name === "QuotaExceededError") return true;
  if (error.name === "NS_ERROR_DOM_QUOTA_REACHED") return true;
  const code = (error as { code?: number }).code;
  return code === 22 || code === 1014;
}

/** 只保留期望键、丢掉多余键的辅助函数，供各 feature 的 parse 复用。 */
export function asRecord(raw: unknown): Record<string, unknown> | null {
  return typeof raw === "object" && raw !== null && !Array.isArray(raw)
    ? (raw as Record<string, unknown>)
    : null;
}

export function asIntInRange(
  raw: unknown,
  minimum: number,
  maximum: number
): number | null {
  if (typeof raw !== "number" || !Number.isFinite(raw)) return null;
  const rounded = Math.round(raw);
  return rounded >= minimum && rounded <= maximum ? rounded : null;
}

export function asTrimmedString(raw: unknown, maxLength: number): string | null {
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  return trimmed ? trimmed.slice(0, maxLength) : null;
}
