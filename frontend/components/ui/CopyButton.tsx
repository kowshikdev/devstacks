"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "./Button";
import { CheckIcon, CopyIcon } from "./Icon";

export function CopyButton({
  value,
  label = "Copy",
  size = "sm",
  variant = "default",
}: {
  value: string;
  label?: string;
  size?: "sm" | "md";
  variant?: "default" | "invisible";
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard access can be refused; the value stays selectable on screen.
    }
  }

  return (
    <Button
      type="button"
      size={size}
      variant={variant}
      onClick={copy}
      leadingIcon={copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
    >
      {copied ? "Copied" : label}
      <span aria-live="polite" className="visually-hidden">
        {copied ? `${label} succeeded` : ""}
      </span>
    </Button>
  );
}
