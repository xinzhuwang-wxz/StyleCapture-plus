import { PixelButton } from "../../components/PixelUI";
import { WheelPicker } from "./WheelPicker";
import {
  BODY_SHAPES,
  WHEEL_RANGES,
  profileSummary,
  type BodyProfile,
  type WheelKey
} from "./profile";
import "./profile.css";

const BASIC_WHEELS: readonly WheelKey[] = ["age", "height", "weight"];
const MEASUREMENT_WHEELS: readonly WheelKey[] = ["bust", "waist", "hip"];

/** 个人信息二级页：昵称 + 六个滚轮 + 身型标签，实时生成 AI 建议摘要。 */
export function BodyInfoScreen({
  profile,
  onChange,
  onBack,
  onSave
}: {
  profile: BodyProfile;
  onChange: (patch: Partial<BodyProfile>) => void;
  onBack: () => void;
  onSave: () => void;
}) {
  const renderWheel = (key: WheelKey, tone: "violet" | "pink") => {
    const range = WHEEL_RANGES[key];
    return (
      <WheelPicker
        key={key}
        label={range.label}
        unit={range.unit}
        min={range.min}
        max={range.max}
        value={profile[key]}
        tone={tone}
        onChange={(value) => onChange({ [key]: value } as Partial<BodyProfile>)}
      />
    );
  };

  return (
    <div className="pixel-subpage">
      <div className="subpage__header">
        <PixelButton variant="ghost" onClick={onBack} ariaLabel="返回">
          ‹
        </PixelButton>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="pixel-label" style={{ margin: 0 }}>
            身材越准，试穿越像
          </p>
          <h1 className="pixel-title" style={{ margin: 0, fontSize: "1.18rem" }}>
            我的个人信息
          </h1>
        </div>
      </div>

      <label className="profile__nickname">
        <span className="pixel-label">昵称</span>
        <input
          type="text"
          value={profile.name}
          onChange={(event) => onChange({ name: event.target.value })}
        />
        <span aria-hidden="true">✏️</span>
      </label>

      <div className="profile__wheels">
        {BASIC_WHEELS.map((key) => renderWheel(key, "violet"))}
      </div>

      <p className="pixel-label" style={{ marginBottom: "var(--px-2)" }}>
        三围（cm）
      </p>
      <div className="profile__wheels">
        {MEASUREMENT_WHEELS.map((key) => renderWheel(key, "pink"))}
      </div>

      <p className="pixel-label" style={{ marginBottom: "var(--px-2)" }}>
        身型 · AI 会据此调整版型建议
      </p>
      <div className="profile__shapes">
        {BODY_SHAPES.map((shape) => (
          <button
            key={shape}
            type="button"
            data-active={profile.shape === shape ? "true" : undefined}
            onClick={() => onChange({ shape })}
          >
            {shape}
          </button>
        ))}
      </div>

      <div className="profile__summary">{profileSummary(profile)}</div>

      <PixelButton variant="primary" className="w-full" onClick={onSave}>
        保存资料
      </PixelButton>
    </div>
  );
}
