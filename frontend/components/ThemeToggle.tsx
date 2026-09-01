"use client";

import { useEffect, useState } from "react";

import { useTheme, type ThemePreference } from "./ThemeProvider";
import { Menu } from "./ui/Menu";
import { IconButton } from "./ui/Button";
import { CheckIcon, MonitorIcon, MoonIcon, SunIcon } from "./ui/Icon";

const OPTIONS: { value: ThemePreference; label: string; icon: React.ReactNode }[] = [
  { value: "light", label: "Light", icon: <SunIcon /> },
  { value: "dark", label: "Dark", icon: <MoonIcon /> },
  { value: "system", label: "System", icon: <MonitorIcon /> },
];

export function ThemeToggle() {
  const { preference, setPreference } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Before hydration the real preference is unknown, so show a stable icon
  // rather than one that flips on mount.
  const current = mounted ? preference : "system";
  const icon =
    current === "light" ? <SunIcon /> : current === "dark" ? <MoonIcon /> : <MonitorIcon />;

  return (
    <Menu
      label="Theme"
      trigger={({ toggle, open }) => (
        <IconButton
          icon={icon}
          label="Change theme"
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={toggle}
        />
      )}
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          role="menuitemradio"
          aria-checked={current === option.value}
          className="menu__item"
          onClick={() => setPreference(option.value)}
        >
          {option.icon}
          {option.label}
          {current === option.value ? (
            <span className="menu__item__trailing">
              <CheckIcon size={14} />
            </span>
          ) : null}
        </button>
      ))}
    </Menu>
  );
}
