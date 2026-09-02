"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { signOut } from "../lib/supabase/client";
import { Avatar } from "./ui/Avatar";
import { Button, ButtonLink, IconButton } from "./ui/Button";
import {
  ChevronDownIcon,
  DevStacksMark,
  GearIcon,
  GraphIcon,
  InboxIcon,
  MenuIcon,
  PlugIcon,
  SearchIcon,
  SignOutIcon,
  UserIcon,
  UsersIcon,
  XIcon,
} from "./ui/Icon";
import { Menu, MenuDivider, MenuGroupLabel } from "./ui/Menu";
import { ShortcutKeys } from "./ui/Shortcut";

export interface HeaderUser {
  handle: string;
  displayName: string | null;
  email?: string | null;
}

const APP_NAV = [
  { href: "/dashboard", label: "Overview", icon: <GraphIcon size={15} /> },
  { href: "/dashboard/review", label: "Review", icon: <InboxIcon size={15} /> },
  { href: "/dashboard/connections", label: "Connections", icon: <PlugIcon size={15} /> },
  { href: "/dashboard/settings", label: "Settings", icon: <GearIcon size={15} /> },
];

const COMMUNITY_LINK = { href: "/community", label: "Community", icon: <UsersIcon size={15} /> };

const MARKETING_NAV = [
  { href: "/#how-it-works", label: "How it works", icon: null },
  { href: "/community", label: "Community", icon: null },
  { href: "/#assurance", label: "Assurance", icon: null },
  { href: "/try", label: "Live preview", icon: null },
];

function openPalette() {
  window.dispatchEvent(new CustomEvent("devstacks:open-palette"));
}

export function SiteHeader({ user, variant = "app" }: { user?: HeaderUser | null; variant?: "app" | "marketing" }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  // A route change should never leave the mobile drawer hanging open.
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const nav = variant === "app" ? [...APP_NAV, COMMUNITY_LINK] : MARKETING_NAV;

  return (
    <>
      <header className="header">
        <div className="container header__inner">
          <Link href={user ? "/dashboard" : "/"} className="wordmark">
            <DevStacksMark className="wordmark__mark" />
            DevStacks
          </Link>

          <nav className="header__nav" aria-label="Primary">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="header__nav-link"
                aria-current={pathname === item.href ? "page" : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="header__spacer" />

          <button type="button" className="search-trigger" onClick={openPalette}>
            <SearchIcon size={15} />
            Search
            <span className="search-trigger__keys">
              <ShortcutKeys letter="K" />
            </span>
          </button>

          <div className="header__actions">
            <IconButton
              icon={<SearchIcon />}
              label="Search"
              onClick={openPalette}
              className="hide-md"
            />

            {user ? (
              <Menu
                label="Account"
                trigger={({ toggle, open }) => (
                  <button
                    type="button"
                    className="header__user-trigger"
                    onClick={toggle}
                    aria-haspopup="menu"
                    aria-expanded={open}
                    aria-label="Open account menu"
                  >
                    <Avatar name={user.displayName ?? user.handle} size={26} />
                    <ChevronDownIcon size={14} />
                  </button>
                )}
              >
                <MenuGroupLabel>Signed in as</MenuGroupLabel>
                <div className="menu__item" style={{ pointerEvents: "none" }}>
                  <Avatar name={user.displayName ?? user.handle} size={24} />
                  <span className="flex-1 truncate">
                    <span className="font-semibold">{user.displayName ?? user.handle}</span>
                    <br />
                    <span className="text-xs text-muted">@{user.handle}</span>
                  </span>
                </div>
                <MenuDivider />
                <Link className="menu__item" href={`/${user.handle}`} role="menuitem">
                  <UserIcon size={15} />
                  Your public profile
                </Link>
                {APP_NAV.map((item) => (
                  <Link key={item.href} className="menu__item" href={item.href} role="menuitem">
                    {item.icon}
                    {item.label}
                  </Link>
                ))}
                <MenuDivider />
                <button
                  type="button"
                  role="menuitem"
                  className="menu__item menu__item--danger"
                  onClick={() => {
                    void signOut().then(() => {
                      window.location.href = "/login";
                    });
                  }}
                >
                  <SignOutIcon size={15} />
                  Sign out
                </button>
              </Menu>
            ) : (
              <div className="row gap-2">
                <ButtonLink href="/login" variant="invisible" size="sm" className="hide-sm-btn">
                  Sign in
                </ButtonLink>
                <ButtonLink href="/login?intent=sign-up" variant="primary" size="sm">
                  Get started
                </ButtonLink>
              </div>
            )}

            <IconButton
              className="header__menu-toggle"
              icon={mobileOpen ? <XIcon /> : <MenuIcon />}
              label={mobileOpen ? "Close navigation" : "Open navigation"}
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen((value) => !value)}
            />
          </div>
        </div>
      </header>

      {mobileOpen ? (
        <div className="mobile-nav">
          <div className="container">
            <ul className="mobile-nav__list">
              {nav.map((item) => (
                <li key={item.href}>
                  <Link href={item.href} className="mobile-nav__link">
                    {item.icon}
                    {item.label}
                  </Link>
                </li>
              ))}
              {user ? (
                <li>
                  <Link href={`/${user.handle}`} className="mobile-nav__link">
                    <UserIcon size={15} />
                    Your public profile
                  </Link>
                </li>
              ) : (
                <li className="mt-4">
                  <Button
                    variant="primary"
                    block
                    onClick={() => {
                      window.location.href = "/login";
                    }}
                  >
                    Sign in
                  </Button>
                </li>
              )}
            </ul>
          </div>
        </div>
      ) : null}
    </>
  );
}
