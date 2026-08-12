import { useState } from "react";

import { PixelButton } from "../../components/PixelUI";
import { MetricWheel } from "./MetricWheel";
import {
  BODY_SHAPES,
  METRIC_FIELDS,
  clampMetric,
  defaultMetricValue,
  writeBodyProfile,
  type BodyProfile
} from "./profileStorage";

type BodyProfileSheetProps = {
  profile: BodyProfile;
  onSaved: (profile: BodyProfile) => void;
  onClose: () => void;
  onNotice?: (message: string) => void;
};

/**
 * 「我的个人信息」二级页。
 *
 * 这些数字只用来让版型建议和真人上身效果更准。
 */
export function BodyProfileSheet({
  profile,
  onSaved,
  onClose,
  onNotice
}: BodyProfileSheetProps) {
  const [draft, setDraft] = useState<BodyProfile>(profile);
  const [error, setError] = useState<string | null>(null);

  function setMetric(key: (typeof METRIC_FIELDS)[number]["key"], value: number) {
    setDraft((current) => ({ ...current, [key]: clampMetric(key, value) }));
  }

  function save() {
    const nickname = draft.nickname.trim();
    if (!nickname) {
      setError("给自己起个昵称吧");
      return;
    }
    const next = { ...draft, nickname };
    const result = writeBodyProfile(next);
    if (!result.ok) {
      // 存不下就要说出来，不能让用户以为保存成功了。
      setError(
        result.reason === "quota"
          ? "本机存储空间不足，先删几张形象照再保存"
          : "这台设备不允许保存资料，换个浏览器或关掉无痕模式试试"
      );
      return;
    }
    setError(null);
    onSaved(next);
    onNotice?.("身材资料已保存");
    onClose();
  }

  return (
    <section className="profile-page" aria-label="我的个人信息">
      <div className="subpage__header">
        <PixelButton variant="ghost" onClick={onClose}>
          ‹ 返回
        </PixelButton>
        <h1 className="pixel-title" style={{ margin: 0 }}>
          我的个人信息
        </h1>
      </div>

      <div className="profile__nickname">
        <span className="pixel-label">昵称</span>
        <input
          value={draft.nickname}
          maxLength={12}
          aria-label="昵称"
          placeholder="给自己起个名字"
          onChange={(event) =>
            setDraft((current) => ({ ...current, nickname: event.target.value }))
          }
        />
      </div>

      <div className="profile__section-head">
        <h2 className="pixel-subtitle" style={{ margin: 0 }}>
          基础信息
        </h2>
      </div>
      <div className="profile__wheels">
        {METRIC_FIELDS.filter((field) => field.group === "a").map((field) => {
          const value = draft[field.key];
          return typeof value === "number" ? (
            <MetricWheel
              key={field.key}
              field={field}
              value={value}
              onChange={(next) => setMetric(field.key, next)}
            />
          ) : null;
        })}
      </div>

      <div className="profile__section-head">
        <h2 className="pixel-subtitle" style={{ margin: 0 }}>
          三围（cm）
        </h2>
        <span className="pixel-label">选填，不清楚可留空</span>
      </div>
      <div className="profile__wheels">
        {METRIC_FIELDS.filter((field) => field.group === "b").map((field) => {
          const value = draft[field.key];
          return value === null ? (
            <button
              key={field.key}
              type="button"
              className="profile__metric-empty"
              aria-label={`填写${field.label}`}
              onClick={() =>
                setMetric(field.key, defaultMetricValue(field.key))
              }
            >
              <span>{field.label}</span>
              <strong>＋ 填写</strong>
              <small>选填</small>
            </button>
          ) : (
            <MetricWheel
              key={field.key}
              field={field}
              value={value}
              onChange={(next) => setMetric(field.key, next)}
              onClear={() =>
                setDraft((current) => ({ ...current, [field.key]: null }))
              }
            />
          );
        })}
      </div>

      <div className="profile__section-head">
        <h2 className="pixel-subtitle" style={{ margin: 0 }}>
          身型
        </h2>
        <span className="pixel-label">选填，AI 会据此调整建议</span>
      </div>
      <div className="profile__shapes" role="group" aria-label="身型">
        {BODY_SHAPES.map((shape) => (
          <button
            key={shape}
            type="button"
            data-active={draft.shape === shape ? "true" : undefined}
            aria-pressed={draft.shape === shape}
            onClick={() =>
              setDraft((current) => ({
                ...current,
                shape: current.shape === shape ? null : shape
              }))
            }
          >
            {shape}
          </button>
        ))}
      </div>

      {error ? (
        <div className="profile__error" role="alert">
          {error}
        </div>
      ) : null}

      <div className="profile__actions profile__actions--save">
        <PixelButton
          variant="primary"
          className="profile__save-button"
          onClick={save}
        >
          保存资料
        </PixelButton>
      </div>
    </section>
  );
}
