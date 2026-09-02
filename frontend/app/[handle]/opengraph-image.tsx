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
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 44,
              height: 44,
              borderRadius: 12,
              background: FG,
              color: CANVAS,
              fontSize: 24,
              fontWeight: 700,
            }}
          >
            DS
          </div>
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
