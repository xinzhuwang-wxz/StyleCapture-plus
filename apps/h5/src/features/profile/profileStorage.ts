/**
 * 身材资料的本机存档。
 *
 * 这些数字是用来让 AI 的版型建议和真人上身效果更准的，属于个人身体信息，
 * 所以只留在这台设备上，不进任何请求体。改字段就升版本号，旧存档会被忽略
 * 并回落到默认值，而不是把半截数据喂给界面。
 */

import {
  asIntInRange,
  asRecord,
  asTrimmedString,
  readLocal,
  writeLocal,
  type LocalStoreDefinition,
  type WriteResult
} from "../../storage/localStore";

export type BodyShape = "梨形" | "沙漏形" | "苹果形" | "H 形" | "倒三角";

export const BODY_SHAPES: readonly BodyShape[] = [
  "梨形",
  "沙漏形",
  "苹果形",
  "H 形",
  "倒三角"
];

/** 每项的取值范围就是滚轮的刻度范围，两边共用同一份定义。 */
export type MetricField = {
  readonly key: "age" | "height" | "weight" | "bust" | "waist" | "hip";
  readonly label: string;
  readonly unit: string;
  readonly min: number;
  readonly max: number;
  /** a 组是基础三项，b 组是三围；界面上分两排。 */
  readonly group: "a" | "b";
};

export const METRIC_FIELDS: readonly MetricField[] = [
  { key: "age", label: "年龄", unit: "岁", min: 16, max: 45, group: "a" },
  { key: "height", label: "身高", unit: "cm", min: 145, max: 185, group: "a" },
  { key: "weight", label: "体重", unit: "kg", min: 36, max: 78, group: "a" },
  { key: "bust", label: "胸围", unit: "cm", min: 70, max: 102, group: "b" },
  { key: "waist", label: "腰围", unit: "cm", min: 54, max: 88, group: "b" },
  { key: "hip", label: "臀围", unit: "cm", min: 74, max: 108, group: "b" }
];

export type BodyProfile = {
  nickname: string;
  age: number;
  height: number;
  weight: number;
  bust: number | null;
  waist: number | null;
  hip: number | null;
  shape: BodyShape | null;
};

const NICKNAME_MAX = 12;
const METRIC_DEFAULTS: Record<MetricField["key"], number> = {
  age: 24,
  height: 165,
  weight: 48,
  bust: 84,
  waist: 64,
  hip: 90
};

export function defaultMetricValue(key: MetricField["key"]): number {
  return METRIC_DEFAULTS[key];
}

export function defaultBodyProfile(): BodyProfile {
  return {
    nickname: "我",
    age: METRIC_DEFAULTS.age,
    height: METRIC_DEFAULTS.height,
    weight: METRIC_DEFAULTS.weight,
    bust: null,
    waist: null,
    hip: null,
    shape: null
  };
}

function fieldRange(key: MetricField["key"]): MetricField {
  const field = METRIC_FIELDS.find((entry) => entry.key === key);
  if (!field) throw new Error(`unknown metric ${key}`);
  return field;
}

/** 把任意数字夹到该项的合法范围内，供滚轮与输入框共用。 */
export function clampMetric(key: MetricField["key"], value: number): number {
  const { min, max } = fieldRange(key);
  if (!Number.isFinite(value)) return defaultMetricValue(key);
  return Math.min(max, Math.max(min, Math.round(value)));
}

export const bodyProfileStore: LocalStoreDefinition<BodyProfile> = {
  key: "stylecapture:body-profile:v1",
  fallback: defaultBodyProfile,
  parse: (raw) => {
    const record = asRecord(raw);
    if (!record) return null;

    const nickname = asTrimmedString(record.nickname, NICKNAME_MAX);
    if (!nickname) return null;

    const shape =
      record.shape === null
        ? null
        : BODY_SHAPES.find((entry) => entry === record.shape) ?? undefined;
    if (shape === undefined) return null;

    const metrics: Partial<Record<MetricField["key"], number | null>> = {};
    for (const field of METRIC_FIELDS) {
      if (field.group === "b" && record[field.key] === null) {
        metrics[field.key] = null;
        continue;
      }
      const value = asIntInRange(record[field.key], field.min, field.max);
      if (value === null) return null;
      metrics[field.key] = value;
    }

    return {
      nickname,
      shape,
      age: metrics.age!,
      height: metrics.height!,
      weight: metrics.weight!,
      bust: metrics.bust ?? null,
      waist: metrics.waist ?? null,
      hip: metrics.hip ?? null
    };
  }
};

export function readBodyProfile(): BodyProfile {
  return readLocal(bodyProfileStore);
}

export function writeBodyProfile(profile: BodyProfile): WriteResult {
  return writeLocal(bodyProfileStore, profile);
}

/**
 * 资料是否还是原封不动的默认值。
 *
 * 用来决定要不要提示「补全身材数据，AI 生成的上身效果更准」——已经填过的人
 * 不该再被催一次。
 */
export function isDefaultBodyProfile(profile: BodyProfile): boolean {
  const base = defaultBodyProfile();
  return (
    Object.keys(base) as (keyof BodyProfile)[]
  ).every((key) => profile[key] === base[key]);
}
