/** 用户身材档案。AI 会据此调整版型建议和真人试穿的比例。 */
export type BodyProfile = {
  name: string;
  age: number;
  height: number;
  weight: number;
  bust: number;
  waist: number;
  hip: number;
  shape: string;
};

export const DEFAULT_PROFILE: BodyProfile = {
  name: "小甜甜",
  age: 24,
  height: 165,
  weight: 48,
  bust: 84,
  waist: 64,
  hip: 90,
  shape: "梨形"
};

export const BODY_SHAPES: readonly string[] = ["梨形", "沙漏形", "苹果形", "H 形", "倒三角"];

/** 每个滚轮的取值范围，超出范围的输入没有意义。 */
export const WHEEL_RANGES = {
  age: { label: "年龄", unit: "岁", min: 16, max: 45 },
  height: { label: "身高", unit: "cm", min: 145, max: 185 },
  weight: { label: "体重", unit: "kg", min: 36, max: 78 },
  bust: { label: "胸围", unit: "cm", min: 70, max: 102 },
  waist: { label: "腰围", unit: "cm", min: 54, max: 88 },
  hip: { label: "臀围", unit: "cm", min: 74, max: 108 }
} as const;

export type WheelKey = keyof typeof WHEEL_RANGES;

export function profileSummary(profile: BodyProfile): string {
  return (
    `身高 ${profile.height}cm · 体重 ${profile.weight}kg · ` +
    `${profile.bust}/${profile.waist}/${profile.hip} · ${profile.shape}，` +
    "AI 会优先推荐收腰、显腿长的版型。"
  );
}
