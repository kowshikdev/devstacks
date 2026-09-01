import type { ReactNode } from "react";

export type LabelTone =
  | "neutral"
  | "accent"
  | "success"
  | "attention"
  | "danger"
  | "info"
  | "done";

export function Label({
  tone = "neutral",
  mono,
  size,
  children,
  className,
}: {
  tone?: LabelTone;
  mono?: boolean;
  size?: "lg";
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={[
        "label",
        tone !== "neutral" ? `label--${tone}` : "",
        mono ? "label--mono" : "",
        size === "lg" ? "label--lg" : "",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </span>
  );
}

export function Counter({
  value,
  tone = "neutral",
}: {
  value: number | string;
  tone?: "neutral" | "accent" | "emphasis";
}) {
  return (
    <span className={["counter", tone !== "neutral" ? `counter--${tone}` : ""].filter(Boolean).join(" ")}>
      {value}
    </span>
  );
}

/**
 * A claim's verification state, mapped to one of three visual states so the
 * whole product reads the same vocabulary.
 */
export function StateLabel({ status, children }: { status: string | null; children?: ReactNode }) {
  const normalized = (status ?? "unknown").toLowerCase();
  const tone =
    normalized === "verified" || normalized === "passed" || normalized === "current"
      ? "verified"
      : normalized === "failed" || normalized === "contradicted" || normalized === "rejected"
        ? "failed"
        : "pending";
  return <span className={`state-label state-label--${tone}`}>{children ?? normalized}</span>;
}
