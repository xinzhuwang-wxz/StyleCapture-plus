import { useState } from "react";

import { PixelButton } from "../../components/PixelUI";
import { MetricWheel } from "./MetricWheel";
import {
  BODY_SHAPES,
  METRIC_FIELDS,
  clampMetric,
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
 * 这些数字只用来让版型建议和真人上身效果更准，所以全程留在本机，界面上也
 * 明说这一点——身体数据要让人一眼看出去了哪里。
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
    onNotice?.("身材资料已保存在本机");
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
        {METRIC_FIELDS.filter((field) => field.group === "a").map((field) => (
          <MetricWheel
            key={field.key}
            field={field}
            value={draft[field.key]}
            onChange={(value) => setMetric(field.key, value)}
          />
        ))}
      </div>

      <div className="profile__section-head">
        <h2 className="pixel-subtitle" style={{ margin: 0 }}>
          三围（cm）
        </h2>
      </div>
      <div className="profile__wheels">
        {METRIC_FIELDS.filter((field) => field.group === "b").map((field) => (
          <MetricWheel
            key={field.key}
            field={field}
            value={draft[field.key]}
            onChange={(value) => setMetric(field.key, value)}
          />
        ))}
      </div>

      <div className="profile__section-head">
        <h2 className="pixel-subtitle" style={{ margin: 0 }}>
          身型
        </h2>
        <span className="pixel-label">AI 会据此调整版型建议</span>
      </div>
      <div className="profile__shapes" role="group" aria-label="身型">
        {BODY_SHAPES.map((shape) => (
          <button
            key={shape}
            type="button"
            data-active={draft.shape === shape ? "true" : undefined}
            aria-pressed={draft.shape === shape}
            onClick={() => setDraft((current) => ({ ...current, shape }))}
          >
            {shape}
          </button>
        ))}
      </div>

      <p className="profile__summary">
        身材越准，试穿越像。这些数据只保存在这台设备上，不会上传服务器。
      </p>

      {error ? (
        <div className="profile__error" role="alert">
          {error}
        </div>
      ) : null}

      <div className="profile__actions">
        <PixelButton variant="primary" onClick={save}>
          保存资料
        </PixelButton>
      </div>
    </section>
  );
}
