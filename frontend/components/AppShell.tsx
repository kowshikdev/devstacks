"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { signOut } from "../lib/supabase/client";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/dashboard/connect/github", label: "Connect GitHub" },
  { href: "/dashboard/review", label: "Review" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link href="/dashboard" className="wordmark">
          DevStacks
        </Link>
        <nav className="topnav">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={pathname === item.href ? "topnav-link active" : "topnav-link"}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <button
          type="button"
          className="link-button"
          onClick={() => signOut().then(() => (window.location.href = "/login"))}
        >
          Sign out
        </button>
      </header>
      <div className="shell-body">{children}</div>
    </div>
  );
}
