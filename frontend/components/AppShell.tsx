"use client";

import type { ReactNode } from "react";

import { CommandPalette } from "./CommandPalette";
import { SiteFooter } from "./SiteFooter";
import { SiteHeader, type HeaderUser } from "./SiteHeader";
import { NavTabs, type TabItem } from "./ui/Tabs";
import { GearIcon, GraphIcon, InboxIcon, PlugIcon } from "./ui/Icon";

const SUBNAV: TabItem[] = [
  { href: "/dashboard", label: "Overview", icon: <GraphIcon size={15} /> },
  { href: "/dashboard/review", label: "Review", icon: <InboxIcon size={15} />, prefix: true },
  { href: "/dashboard/connections", label: "Connections", icon: <PlugIcon size={15} />, prefix: true },
  { href: "/dashboard/settings", label: "Settings", icon: <GearIcon size={15} /> },
];

/**
 * The signed-in application frame: global header, product sub-navigation,
 * command palette, and footer. Pages render only their own content.
 */
export default function AppShell({
  children,
  user,
  reviewCount,
}: {
  children: ReactNode;
  user?: HeaderUser | null;
  reviewCount?: number;
}) {
  const subnav = SUBNAV.map((item) =>
    item.href === "/dashboard/review" && reviewCount ? { ...item, count: reviewCount } : item
  );

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <SiteHeader user={user} />
      <div className="subnav">
        <div className="container">
          <NavTabs items={subnav} label="Dashboard sections" />
        </div>
      </div>
      <main className="app-main" id="main">
        <div className="container">{children}</div>
      </main>
      <SiteFooter />
      <CommandPalette />
    </div>
  );
}

/** The public frame: same chrome, no product sub-navigation. */
export function PublicShell({
  children,
  bare,
}: {
  children: ReactNode;
  bare?: boolean;
}) {
  return (
    <div className="app-frame">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <SiteHeader variant="marketing" />
      <main className={bare ? undefined : "app-main"} id="main" style={{ flex: 1 }}>
        {children}
      </main>
      <SiteFooter />
      <CommandPalette />
    </div>
  );
}
