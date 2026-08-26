import { ImageResponse } from "next/og";

import { getPublicProfile } from "../../lib/api/client";

export const alt = "DevStacks verified profile";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  const profile = await getPublicProfile(handle).catch(() => null);

  const displayName = profile?.display_name ?? profile?.handle ?? handle;
  const claimCount = profile?.claims.length ?? 0;
  const topCategory = profile?.claims[0]?.category ?? null;
  const lastVerifiedAt = profile?.claims[0]?.last_verified_at ?? null;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 64,
          background: "#0a0d0c",
          color: "#e9efec",
          fontFamily: "Verdana, Geneva, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ color: "#34d399", fontSize: 24, fontWeight: 700, letterSpacing: -1 }}>
            ▲ DEVSTACKS
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", fontSize: 64, fontWeight: 600, letterSpacing: -2 }}>
            {displayName}
          </div>
          <div style={{ display: "flex", fontSize: 28, color: "#a3b3ab" }}>@{handle}</div>
        </div>

        <div style={{ display: "flex", gap: 20 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              padding: "10px 22px",
              borderRadius: 999,
              border: "1px solid #37423c",
              background: "#121613",
              color: "#34d399",
              fontSize: 24,
              fontWeight: 600,
            }}
          >
            {claimCount} verified claim{claimCount === 1 ? "" : "s"}
          </div>
          {topCategory && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                padding: "10px 22px",
                borderRadius: 999,
                border: "1px solid #37423c",
                background: "#121613",
                color: "#a3b3ab",
                fontSize: 24,
              }}
            >
              {topCategory}
            </div>
          )}
          {lastVerifiedAt && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                padding: "10px 22px",
                borderRadius: 999,
                border: "1px solid #37423c",
                background: "#121613",
                color: "#64766e",
                fontSize: 24,
              }}
            >
              last verified {lastVerifiedAt.slice(0, 10)}
            </div>
          )}
        </div>
      </div>
    ),
    { ...size }
  );
}
