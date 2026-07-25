import { type ReactNode, useCallback, useRef, useState } from "react";

// ─── Pixel Button ──────────────────────────────────────

export function PixelButton({
  children,
  variant = "default",
  disabled,
  className = "",
  onClick,
  type = "button",
  ariaLabel
}: {
  children: ReactNode;
  variant?: "default" | "primary" | "accent" | "ghost";
  disabled?: boolean;
  className?: string;
  onClick?: () => void;
  type?: "button" | "submit";
  ariaLabel?: string;
}) {
  return (
    <button
      type={type}
      aria-label={ariaLabel}
      disabled={disabled}
      className={`pixel-button pixel-button--${variant} ${className}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

// ─── Pixel Card ────────────────────────────────────────

export function PixelCard({
  children,
  className = "",
  onClick,
  onLongPress,
  ariaLabel
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  onLongPress?: () => void;
  ariaLabel?: string;
}) {
  const timerRef = useRef<number | null>(null);
  const [pressing, setPressing] = useState(false);

  const startPress = useCallback(() => {
    setPressing(true);
    if (onLongPress) {
      timerRef.current = window.setTimeout(() => {
        setPressing(false);
        onLongPress();
      }, 600);
    }
  }, [onLongPress]);

  const endPress = useCallback(() => {
    setPressing(false);
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const handleClick = useCallback(() => {
    if (!pressing && onClick) onClick();
  }, [onClick, pressing]);

  return (
    <article
      className={`pixel-card ${pressing ? "is-pressing" : ""} ${className}`}
      style={{ transform: pressing ? "scale(0.97)" : undefined }}
      aria-label={ariaLabel}
      onClick={handleClick}
      onPointerDown={startPress}
      onPointerUp={endPress}
      onPointerLeave={endPress}
      onContextMenu={(e) => e.preventDefault()}
    >
      {children}
    </article>
  );
}

// ─── Pixel Badge ───────────────────────────────────────

export function PixelBadge({
  variant,
  children
}: {
  variant: "star" | "heart";
  children: ReactNode;
}) {
  return (
    <span className={`pixel-badge pixel-badge--${variant}`} aria-hidden="true">
      {children}
    </span>
  );
}

// ─── Pixel Section Header ──────────────────────────────

export function PixelSectionHeader({
  kicker,
  title,
  action
}: {
  kicker?: string;
  title: string;
  action?: ReactNode;
}) {
  return (
    <div className="pixel-section-header">
      <div>
        {kicker ? <p className="pixel-label">{kicker}</p> : null}
        <h2 className="pixel-title" style={{ fontSize: "1.15rem", margin: 0 }}>
          {title}
        </h2>
      </div>
      {action}
    </div>
  );
}

// ─── Pixel Toast ───────────────────────────────────────

export function PixelToast({
  message,
  variant = "default"
}: {
  message: string;
  variant?: "default" | "success" | "error";
}) {
  return (
    <div className={`pixel-toast pixel-toast--${variant}`} role="alert">
      {message}
    </div>
  );
}

// ─── Pixel Empty State ─────────────────────────────────

export function PixelEmpty({
  icon,
  title,
  description
}: {
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <div className="pixel-empty">
      <span className="pixel-empty__icon">{icon}</span>
      <div>
        <h3 className="pixel-subtitle">{title}</h3>
        <p style={{ color: "var(--pixel-text-dim)", fontSize: "0.78rem", margin: 0 }}>
          {description}
        </p>
      </div>
    </div>
  );
}

// ─── Pixel Filter ──────────────────────────────────────

export function PixelFilter<T extends string>({
  options,
  value,
  onChange
}: {
  options: readonly [T, string][];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="pixel-filter" role="group" aria-label="筛选">
      {options.map(([key, label]) => (
        <button
          key={key}
          type="button"
          className={value === key ? "is-selected" : ""}
          onClick={() => onChange(key)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
