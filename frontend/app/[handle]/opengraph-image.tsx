import { ImageResponse } from "next/og";

import { getPublicProfile } from "../../lib/api/client";

export const alt = "DevStacks verified profile";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const CANVAS = "#0b0f0e";
const SURFACE = "#141b18";
const BORDER = "#26302b";
const FG = "#e7efec";
const MUTED = "#9db0a8";
const BRAND = "#34d399";

function Pill({
  children,
  color = MUTED,
  border = BORDER,
}: {
  children: string;
  color?: string;
  border?: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        padding: "12px 26px",
        borderRadius: 999,
        border: `1px solid ${border}`,
        background: SURFACE,
        color,
        fontSize: 26,
        fontWeight: 600,
      }}
    >
      {children}
    </div>
  );
}

export default async function Image({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  const profile = await getPublicProfile(handle).catch(() => null);

  const displayName = profile?.display_name ?? profile?.handle ?? handle;
  const claims = profile?.claims ?? [];
  const verifiedCount = claims.filter((claim) => claim.assurance_class === "verified").length;
  const topCategory = claims[0]?.category ?? null;
  const lastVerifiedAt = claims[0]?.last_verified_at ?? null;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 72,
          background: CANVAS,
          color: FG,
          fontFamily: "Verdana, Geneva, sans-serif",
        }}
      >
        {/* Brand lockup */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* The mark, drawn inline: the OG renderer has no access to the app's CSS. */}
          <svg width="44" height="44" viewBox="0 0 32 32">
            <path d="M16 4.5 27 10.2 16 15.9 5 10.2Z" fill={BRAND} />
            <path d="M16 18.6 25.4 13.7 27 14.6 16 20.3 5 14.6 6.6 13.7Z" fill="#c9d6d1" />
            <path d="M16 23 25.4 18.1 27 19 16 24.7 5 19 6.6 18.1Z" fill="#8b9c95" />
          </svg>
          <div style={{ display: "flex", fontSize: 24, fontWeight: 700, letterSpacing: 1 }}>
            DEVSTACKS
          </div>
          <div style={{ display: "flex", color: MUTED, fontSize: 22 }}>
            · verified developer evidence
          </div>
        </div>

        {/* Identity */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", fontSize: 68, fontWeight: 700, letterSpacing: -2 }}>
            {displayName}
          </div>
          <div style={{ display: "flex", fontSize: 30, color: MUTED }}>@{handle}</div>
        </div>

        {/* Proof */}
        <div style={{ display: "flex", gap: 18 }}>
          <Pill color={BRAND} border="rgba(52, 211, 153, 0.35)">
            {`${verifiedCount} verified claim${verifiedCount === 1 ? "" : "s"}`}
          </Pill>
          {topCategory ? <Pill>{topCategory}</Pill> : null}
          {lastVerifiedAt ? <Pill>{`last verified ${lastVerifiedAt.slice(0, 10)}`}</Pill> : null}
        </div>
      </div>
    ),
    { ...size }
  );
}
