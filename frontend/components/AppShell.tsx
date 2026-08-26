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
          <svg className="wordmark-mark" viewBox="0 0 26 26" fill="none" aria-hidden="true">
            <circle cx="6" cy="13" r="3.4" stroke="#e9efec" strokeWidth="1.6" />
            <circle cx="20" cy="6" r="2.6" fill="#34d399" />
            <circle cx="20" cy="20" r="2.6" fill="#34d399" />
            <path d="M9 11.6L17.2 7.3M9 14.4L17.2 18.7" stroke="#37423c" strokeWidth="1.4" />
          </svg>
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
