"use client";

import { useEffect, useState } from "react";

import { formatAbsolute, formatRelative } from "../../lib/format/time";

/**
 * Renders the relative form only after hydration. The server render and the
 * first client render both emit the absolute date, so the two always agree.
 */
export function RelativeTime({ value, className }: { value: string; className?: string }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const absolute = formatAbsolute(value);
  return (
    <time dateTime={value} title={absolute} className={className}>
      {mounted ? formatRelative(value) : absolute}
    </time>
  );
}
