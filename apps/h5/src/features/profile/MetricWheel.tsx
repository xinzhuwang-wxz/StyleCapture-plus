import { useEffect, useRef, type KeyboardEvent } from "react";

import type { MetricField } from "./profileStorage";

/** 必须和 profile.css 里 .wheel__option 的高度一致，滚动位置靠它换算。 */
const OPTION_HEIGHT = 34;

type MetricWheelProps = {
  field: MetricField;
  value: number;
  onChange: (value: number) => void;
};

/**
 * 身材数值的滚轮选择器。
 *
 * 视觉上是一列可滚动的数字，中间高亮那一格就是当前值——手指滑动最顺手。但
 * 滚动列表对键盘和读屏是不可用的，所以这里同时声明成 spinbutton：有
 * aria-valuenow/min/max，能用上下键、翻页键、Home/End 调整。两条路径改的是
 * 同一个值，不存在只有某一种输入方式才能填的字段。
 */
export function MetricWheel({ field, value, onChange }: MetricWheelProps) {
  const listRef = useRef<HTMLDivElement>(null);
  // 区分「用户在滑」和「我们把列表滚到位」，否则程序化滚动会回弹成一次改值。
  const settling = useRef(false);
  const tone = field.group === "a" ? "violet" : "pink";

  const options: number[] = [];
  for (let step = field.min; step <= field.max; step += 1) options.push(step);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const target = (value - field.min) * OPTION_HEIGHT;
    if (Math.abs(list.scrollTop - target) < 1) return;
    settling.current = true;
    // 直接赋值而不是 scrollTo：这里本来就要求瞬时到位，少一个可选 API 依赖。
    list.scrollTop = target;
    // 一帧之后再放行，跳过这次滚动产生的事件。
    const timer = window.setTimeout(() => {
      settling.current = false;
    }, 0);
    return () => window.clearTimeout(timer);
  }, [value, field.min]);

  function handleScroll() {
    if (settling.current) return;
    const list = listRef.current;
    if (!list) return;
    const index = Math.round(list.scrollTop / OPTION_HEIGHT);
    const next = Math.min(field.max, Math.max(field.min, field.min + index));
    if (next !== value) onChange(next);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const steps: Record<string, number> = {
      ArrowUp: 1,
      ArrowRight: 1,
      ArrowDown: -1,
      ArrowLeft: -1,
      PageUp: 5,
      PageDown: -5
    };
    let next: number | null = null;
    if (event.key in steps) next = value + steps[event.key];
    else if (event.key === "Home") next = field.min;
    else if (event.key === "End") next = field.max;
    if (next === null) return;
    event.preventDefault();
    onChange(Math.min(field.max, Math.max(field.min, next)));
  }

  return (
    <div className="wheel">
      <p className="wheel__label">{field.label}</p>
      <div className={`wheel__highlight wheel__highlight--${tone}`} aria-hidden="true" />
      <div
        ref={listRef}
        className="wheel__list"
        role="spinbutton"
        tabIndex={0}
        aria-label={field.label}
        aria-valuemin={field.min}
        aria-valuemax={field.max}
        aria-valuenow={value}
        aria-valuetext={`${value} ${field.unit}`}
        onScroll={handleScroll}
        onKeyDown={handleKeyDown}
      >
        {options.map((option) => (
          <div
            key={option}
            className="wheel__option"
            data-active={option === value ? "true" : undefined}
            aria-hidden="true"
          >
            {option}
          </div>
        ))}
      </div>
      <p className={`wheel__unit wheel__unit--${tone}`}>{field.unit}</p>
    </div>
  );
}
