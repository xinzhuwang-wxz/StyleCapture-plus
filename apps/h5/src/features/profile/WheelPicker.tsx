import { useCallback, useEffect, useRef } from "react";

/** 每一档的高度，滚动吸附和取值换算都基于它。 */
const ROW_HEIGHT = 34;

/**
 * 滚轮 / 波轮式数值选择器。
 *
 * 用原生滚动 + CSS scroll-snap 实现，因此在真机上有惯性和吸附手感，
 * 不需要手写手势。选中项放大变色，上下用遮罩淡出。
 */
export function WheelPicker({
  label,
  unit,
  min,
  max,
  value,
  tone = "violet",
  onChange
}: {
  label: string;
  unit: string;
  min: number;
  max: number;
  value: number;
  /** 高亮条的配色：基础信息用紫，三围用粉 */
  tone?: "violet" | "pink";
  onChange: (value: number) => void;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const settleTimer = useRef<number | null>(null);

  const options = [];
  for (let candidate = min; candidate <= max; candidate += 1) options.push(candidate);

  // 打开这一页时把滚轮滚到当前值。字体加载会改变布局，所以补一次延迟校正。
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const top = (value - min) * ROW_HEIGHT;
    list.scrollTop = top;
    const retry = window.setTimeout(() => {
      list.scrollTop = top;
    }, 60);
    return () => window.clearTimeout(retry);
    // 只在挂载时对齐；之后由用户滚动驱动。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleScroll = useCallback(() => {
    const list = listRef.current;
    if (!list) return;
    if (settleTimer.current !== null) window.clearTimeout(settleTimer.current);
    // 等吸附停稳再取值，滚动过程中不会疯狂刷新父组件
    settleTimer.current = window.setTimeout(() => {
      const next = Math.min(max, Math.max(min, min + Math.round(list.scrollTop / ROW_HEIGHT)));
      if (next !== value) onChange(next);
    }, 90);
  }, [max, min, onChange, value]);

  useEffect(
    () => () => {
      if (settleTimer.current !== null) window.clearTimeout(settleTimer.current);
    },
    []
  );

  return (
    <div className="wheel">
      <p className="wheel__label">{label}</p>
      <div className={`wheel__highlight wheel__highlight--${tone}`} aria-hidden="true" />
      <div
        ref={listRef}
        className="wheel__list"
        role="spinbutton"
        aria-label={`${label}（${unit}）`}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
        tabIndex={0}
        onScroll={handleScroll}
        onKeyDown={(event) => {
          if (event.key === "ArrowUp") {
            event.preventDefault();
            onChange(Math.max(min, value - 1));
          }
          if (event.key === "ArrowDown") {
            event.preventDefault();
            onChange(Math.min(max, value + 1));
          }
        }}
      >
        {options.map((option) => {
          const distance = Math.abs(option - value);
          return (
            <div
              key={option}
              className="wheel__option"
              data-active={distance === 0 ? "true" : undefined}
              style={{ opacity: distance === 0 ? 1 : distance === 1 ? 0.7 : 0.35 }}
            >
              {option}
            </div>
          );
        })}
      </div>
      <p className={`wheel__unit wheel__unit--${tone}`}>{unit}</p>
    </div>
  );
}
