import type { ReactNode } from "react";

import { AlertIcon, CheckCircleIcon, InfoIcon, XCircleIcon } from "./Icon";

export type FlashTone = "neutral" | "success" | "danger" | "attention" | "info";

const FLASH_ICON: Record<FlashTone, ReactNode> = {
  neutral: <InfoIcon />,
  success: <CheckCircleIcon />,
  danger: <XCircleIcon />,
  attention: <AlertIcon />,
  info: <InfoIcon />,
};

export function Flash({
  tone = "neutral",
  children,
  actions,
  role,
}: {
  tone?: FlashTone;
  children: ReactNode;
  actions?: ReactNode;
  role?: "alert" | "status";
}) {
  return (
    <div
      className={["flash", tone !== "neutral" ? `flash--${tone}` : ""].filter(Boolean).join(" ")}
      role={role ?? (tone === "danger" ? "alert" : "status")}
    >
      <span className="shrink-0" style={{ marginTop: 2 }}>
        {FLASH_ICON[tone]}
      </span>
      <div className="flash__body">{children}</div>
      {actions ? <div className="row gap-2 shrink-0">{actions}</div> : null}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon ? <div className="empty-state__icon">{icon}</div> : null}
      <h3 className="empty-state__title">{title}</h3>
      {description ? <p className="empty-state__description">{description}</p> : null}
      {action ? <div className="row gap-2 mt-2">{action}</div> : null}
    </div>
  );
}

export function Skeleton({
  width,
  height = 12,
  radius,
  className,
}: {
  width?: number | string;
  height?: number | string;
  radius?: number;
  className?: string;
}) {
  return (
    <span
      className={["skeleton", className ?? ""].filter(Boolean).join(" ")}
      style={{
        display: "block",
        width: width ?? "100%",
        height,
        borderRadius: radius ?? undefined,
      }}
      aria-hidden="true"
    />
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span className="row gap-2" role="status">
      <span className="spinner" />
      <span className="visually-hidden">{label}</span>
    </span>
  );
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div
      className="progress"
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div className="progress__bar" style={{ width: `${clamped}%` }} />
    </div>
  );
}
