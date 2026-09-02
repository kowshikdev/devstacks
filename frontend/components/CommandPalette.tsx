"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ArrowRightIcon,
  GearIcon,
  GraphIcon,
  InboxIcon,
  MoonIcon,
  PlugIcon,
  SearchIcon,
  SunIcon,
  UserIcon,
  UsersIcon,
} from "./ui/Icon";
import { useTheme } from "./ThemeProvider";

interface Command {
  id: string;
  label: string;
  hint?: string;
  icon: React.ReactNode;
  keywords: string;
  run: () => void;
}

/**
 * ⌘K / Ctrl-K navigation. Anything typed that is not a command is treated as a
 * profile handle, which is the lookup people actually reach for here.
 */
export function CommandPalette() {
  const router = useRouter();
  const { setPreference } = useTheme();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const restoreFocusTo = useRef<HTMLElement | null>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setActiveIndex(0);
  }, []);

  const go = useCallback(
    (href: string) => () => {
      close();
      router.push(href);
    },
    [close, router]
  );

  const commands = useMemo<Command[]>(
    () => [
      {
        id: "dashboard",
        label: "Go to dashboard",
        hint: "Overview",
        icon: <GraphIcon />,
        keywords: "dashboard home overview",
        run: go("/dashboard"),
      },
      {
        id: "review",
        label: "Open review inbox",
        hint: "Pending claims",
        icon: <InboxIcon />,
        keywords: "review inbox claims pending approve",
        run: go("/dashboard/review"),
      },
      {
        id: "connections",
        label: "Manage connections",
        hint: "Connectors",
        icon: <PlugIcon />,
        keywords: "connections connectors github sync integrations",
        run: go("/dashboard/connections"),
      },
      {
        id: "settings",
        label: "Open settings",
        hint: "Profile & account",
        icon: <GearIcon />,
        keywords: "settings profile account handle visibility",
        run: go("/dashboard/settings"),
      },
      {
        id: "community",
        label: "Open community",
        hint: "Spaces",
        icon: <UsersIcon />,
        keywords: "community spaces discussion help jobs forum",
        run: go("/community"),
      },
      {
        id: "preview",
        label: "Preview a GitHub username",
        hint: "No sign-up",
        icon: <UserIcon />,
        keywords: "try preview demo github username",
        run: go("/try"),
      },
      {
        id: "theme-light",
        label: "Switch to light theme",
        icon: <SunIcon />,
        keywords: "theme light appearance day",
        run: () => {
          setPreference("light");
          close();
        },
      },
      {
        id: "theme-dark",
        label: "Switch to dark theme",
        icon: <MoonIcon />,
        keywords: "theme dark appearance night",
        run: () => {
          setPreference("dark");
          close();
        },
      },
    ],
    [go, setPreference, close]
  );

  const trimmed = query.trim();
  const filtered = useMemo(() => {
    if (!trimmed) return commands;
    const needle = trimmed.toLowerCase();
    return commands.filter(
      (command) =>
        command.label.toLowerCase().includes(needle) || command.keywords.includes(needle)
    );
  }, [commands, trimmed]);

  const handleLookup = useCallback(() => {
    const handle = trimmed.replace(/^@/, "").toLowerCase();
    if (!handle) return;
    close();
    router.push(`/${encodeURIComponent(handle)}`);
  }, [trimmed, close, router]);

  const results: Command[] = useMemo(() => {
    if (!trimmed) return filtered;
    return [
      ...filtered,
      {
        id: "lookup",
        label: `Open profile @${trimmed.replace(/^@/, "")}`,
        hint: "Public profile",
        icon: <SearchIcon />,
        keywords: "",
        run: handleLookup,
      },
    ];
  }, [filtered, trimmed, handleLookup]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
    }
    function onOpenRequest() {
      setOpen(true);
    }
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("devstacks:open-palette", onOpenRequest);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("devstacks:open-palette", onOpenRequest);
    };
  }, []);

  useEffect(() => {
    if (!open) {
      restoreFocusTo.current?.focus();
      return;
    }
    restoreFocusTo.current = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  if (!open) return null;

  function onInputKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % Math.max(results.length, 1));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => (index - 1 + results.length) % Math.max(results.length, 1));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      results[activeIndex]?.run();
    }
  }

  return (
    <>
      <div className="overlay-backdrop" onClick={close} aria-hidden="true" />
      <div className="palette" role="dialog" aria-modal="true" aria-label="Command palette">
        <div className="palette__input-row">
          <SearchIcon size={18} />
          <input
            ref={inputRef}
            className="palette__input"
            placeholder="Search commands, or type a handle…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onInputKeyDown}
            aria-label="Search commands or profiles"
            aria-activedescendant={results[activeIndex] ? `palette-${results[activeIndex].id}` : undefined}
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className="kbd">esc</kbd>
        </div>

        <div className="palette__results" role="listbox" aria-label="Results">
          {results.length === 0 ? (
            <p className="text-sm text-muted" style={{ padding: "var(--space-4)" }}>
              No matching command.
            </p>
          ) : (
            results.map((command, index) => (
              <button
                key={command.id}
                id={`palette-${command.id}`}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                data-active={index === activeIndex}
                className="menu__item"
                onMouseEnter={() => setActiveIndex(index)}
                onClick={command.run}
              >
                {command.icon}
                <span className="flex-1 truncate">{command.label}</span>
                {command.hint ? <span className="menu__item__trailing">{command.hint}</span> : null}
                {index === activeIndex ? <ArrowRightIcon size={14} /> : null}
              </button>
            ))
          )}
        </div>

        <div className="palette__footer">
          <span className="palette__hint">
            <kbd className="kbd">↑</kbd>
            <kbd className="kbd">↓</kbd> navigate
          </span>
          <span className="palette__hint">
            <kbd className="kbd">↵</kbd> select
          </span>
          <span className="palette__hint">
            <kbd className="kbd">esc</kbd> close
          </span>
        </div>
      </div>
    </>
  );
}
