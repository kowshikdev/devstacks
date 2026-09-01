"use client";

import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import { useId } from "react";

import { AlertIcon } from "./Icon";

interface FieldShellProps {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  trailingLabel?: ReactNode;
  children: (props: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
}

function FieldShell({ label, hint, error, trailingLabel, children }: FieldShellProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        <span>{label}</span>
        {trailingLabel}
      </label>
      {children({ id, describedBy, invalid: Boolean(error) })}
      {hint && !error ? (
        <p className="field__hint" id={hintId}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p className="field__error" id={errorId}>
          <AlertIcon size={13} />
          {error}
        </p>
      ) : null}
    </div>
  );
}

export type TextFieldProps = {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  trailingLabel?: ReactNode;
  prefix?: string;
  mono?: boolean;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "className">;

export function TextField({
  label,
  hint,
  error,
  trailingLabel,
  prefix,
  mono,
  ...rest
}: TextFieldProps) {
  return (
    <FieldShell label={label} hint={hint} error={error} trailingLabel={trailingLabel}>
      {({ id, describedBy, invalid }) => {
        const input = (
          <input
            id={id}
            className={["input", mono ? "input--mono" : "", invalid ? "input--invalid" : ""]
              .filter(Boolean)
              .join(" ")}
            aria-describedby={describedBy}
            aria-invalid={invalid || undefined}
            {...rest}
          />
        );
        return prefix ? (
          <span className="input-group">
            <span className="input-group__prefix">{prefix}</span>
            {input}
          </span>
        ) : (
          input
        );
      }}
    </FieldShell>
  );
}

export type TextAreaFieldProps = {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  trailingLabel?: ReactNode;
} & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id" | "className">;

export function TextAreaField({ label, hint, error, trailingLabel, ...rest }: TextAreaFieldProps) {
  return (
    <FieldShell label={label} hint={hint} error={error} trailingLabel={trailingLabel}>
      {({ id, describedBy, invalid }) => (
        <textarea
          id={id}
          className={["textarea", invalid ? "textarea--invalid" : ""].filter(Boolean).join(" ")}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          {...rest}
        />
      )}
    </FieldShell>
  );
}

export function Switch({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  return (
    <div className="row row--between gap-4">
      <div className="flex-1">
        <p className="text-sm font-semibold">{label}</p>
        {description ? <p className="text-xs text-muted mt-1">{description}</p> : null}
      </div>
      <button
        type="button"
        role="switch"
        className="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
      >
        <span className="switch__thumb" />
      </button>
    </div>
  );
}
