"use client";

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

/**
 * A dropdown anchored to its trigger. Closes on outside click, on Escape, and
 * on route-affecting selections made inside it.
 */
export function Menu({
  trigger,
  children,
  align = "right",
  label,
}: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  children: ReactNode;
  align?: "left" | "right";
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="header__user" ref={containerRef}>
      {trigger({ open, toggle: () => setOpen((value) => !value) })}
      {open ? (
        <div
          className={["menu", align === "left" ? "menu--left" : ""].filter(Boolean).join(" ")}
          role="menu"
          aria-label={label}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}

export function MenuGroupLabel({ children }: { children: ReactNode }) {
  return <p className="menu__group-label">{children}</p>;
}

export function MenuDivider() {
  return <div className="menu__divider" role="separator" />;
}
