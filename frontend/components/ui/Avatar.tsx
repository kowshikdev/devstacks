/* eslint-disable @next/next/no-img-element */

function initialsOf(name: string): string {
  const parts = name.trim().split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2);
  return (parts[0][0] ?? "") + (parts[1][0] ?? "");
}

export function Avatar({
  name,
  src,
  size = 32,
  square,
  ring,
  className,
}: {
  name: string;
  src?: string | null;
  size?: number;
  square?: boolean;
  ring?: boolean;
  className?: string;
}) {
  return (
    <span
      className={[
        "avatar",
        square ? "avatar--square" : "",
        ring ? "avatar--ring" : "",
        className ?? "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ width: size, height: size, fontSize: Math.max(10, Math.round(size * 0.38)) }}
      aria-hidden="true"
    >
      {src ? <img src={src} alt="" width={size} height={size} loading="lazy" /> : initialsOf(name)}
    </span>
  );
}
