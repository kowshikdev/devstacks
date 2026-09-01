"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export interface TabItem {
  href: string;
  label: string;
  icon?: ReactNode;
  count?: number;
  /** Match nested routes too, not just the exact path. */
  prefix?: boolean;
}

export function NavTabs({ items, label }: { items: TabItem[]; label: string }) {
  const pathname = usePathname();

  return (
    <nav className="tabs" aria-label={label}>
      {items.map((item) => {
        const active = item.prefix
          ? pathname === item.href || pathname.startsWith(`${item.href}/`)
          : pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className="tab"
            aria-current={active ? "page" : undefined}
          >
            {item.icon}
            {item.label}
            {typeof item.count === "number" ? <span className="counter">{item.count}</span> : null}
          </Link>
        );
      })}
    </nav>
  );
}

export function ButtonTabs<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (next: T) => void;
  options: { value: T; label: string; count?: number }[];
  label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className="segmented__item"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
          {typeof option.count === "number" ? ` (${option.count})` : ""}
        </button>
      ))}
    </div>
  );
}
