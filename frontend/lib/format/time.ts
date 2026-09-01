/**
 * Pure time formatters, deliberately outside the "use client" boundary so both
 * server components and client components can call them directly.
 */

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31_536_000_000],
  ["month", 2_592_000_000],
  ["week", 604_800_000],
  ["day", 86_400_000],
  ["hour", 3_600_000],
  ["minute", 60_000],
];

export function formatRelative(iso: string, now = Date.now()): string {
  const timestamp = Date.parse(iso);
  if (Number.isNaN(timestamp)) return "unknown";

  const delta = timestamp - now;
  const absolute = Math.abs(delta);
  if (absolute < 45_000) return "just now";

  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [unit, ms] of UNITS) {
    if (absolute >= ms) {
      return formatter.format(Math.round(delta / ms), unit);
    }
  }
  return "just now";
}

/** UTC-pinned so the server render and the client render never disagree. */
export function formatAbsolute(iso: string): string {
  const timestamp = Date.parse(iso);
  if (Number.isNaN(timestamp)) return iso;
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(timestamp);
}
