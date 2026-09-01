"use client";

import { useEffect, useState } from "react";

/**
 * Renders the platform's own modifier. Showing ⌘ to a Windows or Linux user is
 * a small lie that makes the shortcut unusable, so the glyph is resolved after
 * mount — the server has no way to know the platform.
 */
export function ShortcutKeys({ letter }: { letter: string }) {
  const [apple, setApple] = useState(false);

  useEffect(() => {
    const platform =
      (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform ??
      navigator.platform ??
      "";
    setApple(/mac|iphone|ipad|ipod/i.test(platform));
  }, []);

  return (
    <>
      <kbd className="kbd">{apple ? "⌘" : "Ctrl"}</kbd>
      <kbd className="kbd">{letter}</kbd>
    </>
  );
}
